from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import stripe
import json
import requests
from openai import OpenAI

from .models import UserProfile, Movie, Watchlist, SearchHistory
from .forms import SignUpForm, LoginForm, UserUpdateForm, ProfileUpdateForm, WatchlistForm

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Configure OpenAI
client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None


def home(request):
    """Home page view"""
    context = {
        'user': request.user,
    }
    return render(request, 'cinemai/home.html', context)


def signup_view(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')
            return redirect('login')
    else:
        form = SignUpForm()
    
    return render(request, 'cinemai/signup.html', {'form': form})


def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                next_url = request.GET.get('next', 'home')
                return redirect(next_url)
    else:
        form = LoginForm()
    
    return render(request, 'cinemai/login.html', {'form': form})


@login_required
def logout_view(request):
    """User logout view"""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


@login_required
def account_view(request):
    """User account management view"""
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, instance=request.user.profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your account has been updated!')
            return redirect('account')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=request.user.profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }
    return render(request, 'cinemai/account.html', context)


@login_required
def delete_account(request):
    """Delete user account"""
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, 'Your account has been deleted.')
        return redirect('home')
    return render(request, 'cinemai/delete_account.html')


def search_movies(request):
    """AI-powered movie search view - accessible to all users"""
    movies = []
    search_query = ''
    
    print(f"DEBUG: Request method: {request.method}")
    
    if request.method == 'POST':
        search_query = request.POST.get('search_query', '')
        genre = request.POST.get('genre', '')
        
        print(f"DEBUG: Search query: {search_query}")
        
        # Save search history only for authenticated users
        if request.user.is_authenticated:
            SearchHistory.objects.create(
                user=request.user,
                query=search_query,
                genre=genre
            )
        
        if search_query:
            try:
                from .tmdb_service import TMDBService
                tmdb = TMDBService()
                
                # Check if OpenAI is available for smart search
                if client and settings.OPENAI_API_KEY:
                    print("DEBUG: Using OpenAI + TMDB for intelligent search")
                    
                    # Use OpenAI to understand the query and suggest movies
                    try:
                        prompt = f"""Based on this search query: "{search_query}"
                        
Suggest 8-10 specific movie titles that match this request. Consider:
- Genre preferences
- Themes and plot elements
- Mood and tone
- Similar movies if mentioned

Return ONLY movie titles, one per line, no numbering or explanation."""

                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {"role": "system", "content": "You are a movie recommendation expert. Provide accurate, specific movie titles."},
                                {"role": "user", "content": prompt}
                            ],
                            max_tokens=200,
                            temperature=0.7
                        )
                        
                        movie_titles = response.choices[0].message.content.strip().split('\n')
                        print(f"DEBUG: OpenAI suggested {len(movie_titles)} movies")
                        
                        # Search TMDB for each suggested movie
                        for title in movie_titles[:10]:
                            title = title.strip('0123456789. -•')
                            if title:
                                print(f"DEBUG: Searching TMDB for: {title}")
                                results = tmdb.search_movies(title)
                                
                                # Get the best match (first result)
                                if results.get('results'):
                                    movie_data = results['results'][0]
                                    tmdb_id = movie_data.get('id')
                                    
                                    # Get streaming providers
                                    providers = tmdb.get_watch_providers(tmdb_id, region='GB')
                                    
                                    # Get or create movie
                                    movie, created = Movie.objects.get_or_create(
                                        tmdb_id=tmdb_id,
                                        defaults={
                                            'title': movie_data.get('title', ''),
                                            'year': int(movie_data.get('release_date', '0000')[:4]) if movie_data.get('release_date') else None,
                                            'plot': movie_data.get('overview', ''),
                                            'poster_url': tmdb.get_poster_url(movie_data.get('poster_path')),
                                            'backdrop_url': tmdb.get_backdrop_url(movie_data.get('backdrop_path')),
                                            'rating': movie_data.get('vote_average'),
                                            'popularity': movie_data.get('popularity'),
                                            'vote_count': movie_data.get('vote_count'),
                                            'genre': ', '.join([str(g) for g in movie_data.get('genre_ids', [])]),
                                            'streaming_providers': providers
                                        }
                                    )
                                    
                                    # Update streaming providers if movie already exists
                                    if not created and not movie.streaming_providers:
                                        movie.streaming_providers = providers
                                        movie.save()
                                    
                                    movies.append(movie)
                    
                    except Exception as openai_error:
                        print(f"DEBUG: OpenAI error, falling back to TMDB: {openai_error}")
                        # Fall back to direct TMDB search
                        results = tmdb.search_movies(search_query)
                        
                        for movie_data in results.get('results', [])[:10]:
                            tmdb_id = movie_data.get('id')
                            
                            # Get streaming providers
                            providers = tmdb.get_watch_providers(tmdb_id, region='GB')
                            
                            movie, created = Movie.objects.get_or_create(
                                tmdb_id=tmdb_id,
                                defaults={
                                    'title': movie_data.get('title', ''),
                                    'year': int(movie_data.get('release_date', '0000')[:4]) if movie_data.get('release_date') else None,
                                    'plot': movie_data.get('overview', ''),
                                    'poster_url': tmdb.get_poster_url(movie_data.get('poster_path')),
                                    'backdrop_url': tmdb.get_backdrop_url(movie_data.get('backdrop_path')),
                                    'rating': movie_data.get('vote_average'),
                                    'popularity': movie_data.get('popularity'),
                                    'vote_count': movie_data.get('vote_count'),
                                    'genre': ', '.join([str(g) for g in movie_data.get('genre_ids', [])]),
                                    'streaming_providers': providers
                                }
                            )
                            
                            # Update streaming providers if movie already exists
                            if not created and not movie.streaming_providers:
                                movie.streaming_providers = providers
                                movie.save()
                            
                            movies.append(movie)
                
                else:
                    print("DEBUG: Using TMDB-only search (no OpenAI)")
                    # Direct TMDB search if OpenAI not available
                    results = tmdb.search_movies(search_query)
                    
                    for movie_data in results.get('results', [])[:10]:
                        tmdb_id = movie_data.get('id')
                        
                        # Get streaming providers
                        providers = tmdb.get_watch_providers(tmdb_id, region='GB')
                        
                        movie, created = Movie.objects.get_or_create(
                            tmdb_id=tmdb_id,
                            defaults={
                                'title': movie_data.get('title', ''),
                                'year': int(movie_data.get('release_date', '0000')[:4]) if movie_data.get('release_date') else None,
                                'plot': movie_data.get('overview', ''),
                                'poster_url': tmdb.get_poster_url(movie_data.get('poster_path')),
                                'backdrop_url': tmdb.get_backdrop_url(movie_data.get('backdrop_path')),
                                'rating': movie_data.get('vote_average'),
                                'popularity': movie_data.get('popularity'),
                                'vote_count': movie_data.get('vote_count'),
                                'genre': ', '.join([str(g) for g in movie_data.get('genre_ids', [])]),
                                'streaming_providers': providers
                            }
                        )
                        
                        # Update streaming providers if movie already exists
                        if not created and not movie.streaming_providers:
                            movie.streaming_providers = providers
                            movie.save()
                        
                        movies.append(movie)
                
                print(f"DEBUG: Total movies to display: {len(movies)}")
                    
            except Exception as e:
                print(f"DEBUG: Exception occurred: {str(e)}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'Error searching movies: {str(e)}')
    
    context = {
        'movies': movies,
        'search_query': search_query,
    }
    return render(request, 'cinemai/search.html', context)


def movie_detail(request, movie_id):
    """Movie detail page with full info, cast, trailer, and similar movies"""
    movie = get_object_or_404(Movie, id=movie_id)
    
    # Get detailed info from TMDB
    from .tmdb_service import TMDBService
    tmdb = TMDBService()
    
    # Get full movie details (includes cast, crew, videos)
    movie_details = tmdb.get_movie_details(movie.tmdb_id) if movie.tmdb_id else None
    
    # Get similar movies
    similar_movies_data = tmdb.get_similar_movies(movie.tmdb_id) if movie.tmdb_id else {'results': []}
    
    # Process similar movies (save to DB and display)
    similar_movies = []
    for similar_data in similar_movies_data.get('results', [])[:6]:  # Limit to 6
        similar_movie, created = Movie.objects.get_or_create(
            tmdb_id=similar_data.get('id'),
            defaults={
                'title': similar_data.get('title', ''),
                'year': int(similar_data.get('release_date', '0000')[:4]) if similar_data.get('release_date') else None,
                'plot': similar_data.get('overview', ''),
                'poster_url': tmdb.get_poster_url(similar_data.get('poster_path')),
                'backdrop_url': tmdb.get_backdrop_url(similar_data.get('backdrop_path')),
                'rating': similar_data.get('vote_average'),
                'popularity': similar_data.get('popularity'),
                'vote_count': similar_data.get('vote_count'),
            }
        )
        similar_movies.append(similar_movie)
    
    # Extract trailer URL
    trailer_url = None
    if movie_details and 'videos' in movie_details:
        for video in movie_details['videos'].get('results', []):
            if video.get('type') == 'Trailer' and video.get('site') == 'YouTube':
                trailer_url = f"https://www.youtube.com/embed/{video['key']}"
                break
    
    # Extract cast (top 10)
    cast = []
    if movie_details and 'credits' in movie_details:
        cast = movie_details['credits'].get('cast', [])[:10]
    
    # Extract genres
    genres = []
    if movie_details and 'genres' in movie_details:
        genres = [g['name'] for g in movie_details['genres']]
    
    # Check if in watchlist
    in_watchlist = False
    if request.user.is_authenticated:
        in_watchlist = Watchlist.objects.filter(user=request.user, movie=movie).exists()
    
    context = {
        'movie': movie,
        'movie_details': movie_details,
        'trailer_url': trailer_url,
        'cast': cast,
        'genres': genres,
        'similar_movies': similar_movies,
        'in_watchlist': in_watchlist,
    }
    return render(request, 'cinemai/movie_detail.html', context)


@login_required
def watchlist_view(request):
    """User's watchlist view"""
    watchlist_items = Watchlist.objects.filter(user=request.user).select_related('movie')
    
    context = {
        'watchlist_items': watchlist_items,
    }
    return render(request, 'cinemai/watchlist.html', context)


@login_required
def add_to_watchlist(request, movie_id):
    """Add a movie to user's watchlist"""
    movie = get_object_or_404(Movie, id=movie_id)
    
    watchlist_item, created = Watchlist.objects.get_or_create(
        user=request.user,
        movie=movie
    )
    
    if created:
        messages.success(request, f'{movie.title} added to your watchlist!')
    else:
        messages.info(request, f'{movie.title} is already in your watchlist.')
    
    return redirect(request.META.get('HTTP_REFERER', 'watchlist'))


@login_required
def remove_from_watchlist(request, watchlist_id):
    """Remove a movie from user's watchlist"""
    watchlist_item = get_object_or_404(Watchlist, id=watchlist_id, user=request.user)
    movie_title = watchlist_item.movie.title
    watchlist_item.delete()
    
    messages.success(request, f'{movie_title} removed from your watchlist.')
    return redirect('watchlist')


@login_required
def update_watchlist_item(request, watchlist_id):
    """Update watchlist item (watched status, notes)"""
    watchlist_item = get_object_or_404(Watchlist, id=watchlist_id, user=request.user)
    
    if request.method == 'POST':
        form = WatchlistForm(request.POST, instance=watchlist_item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Watchlist item updated!')
            return redirect('watchlist')
    else:
        form = WatchlistForm(instance=watchlist_item)
    
    context = {
        'form': form,
        'watchlist_item': watchlist_item,
    }
    return render(request, 'cinemai/update_watchlist.html', context)


@login_required
def subscription_view(request):
    """Subscription management and Stripe checkout"""
    context = {
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
    }
    return render(request, 'cinemai/subscription.html', context)


@login_required
def create_checkout_session(request):
    """Create Stripe checkout session"""
    if request.method == 'POST':
        data = json.loads(request.body)
        tier = data.get('tier')
        
        # Stripe Price IDs (GBP)
        price_map = {
            'STANDARD': 'price_1T1qc7Iux0tpDCVobkSiqu2K',  # £9.99/month
            'PRO': 'price_1T1qcpIux0tpDCVoUgUoP5td',        # £14.99/month
        }
        
        # Basic is FREE - no Stripe needed
        if tier == 'BASIC':
            return JsonResponse({'error': 'Basic plan is free, no payment needed'}, status=400)
        
        price_id = price_map.get(tier)
        if not price_id:
            return JsonResponse({'error': 'Invalid plan selected'}, status=400)
        
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=request.build_absolute_uri('/subscription/success/'),
                cancel_url=request.build_absolute_uri('/subscription/'),
                client_reference_id=str(request.user.id),
                metadata={
                    'tier': tier,
                    'user_id': str(request.user.id),
                }
            )
            
            return JsonResponse({'sessionId': checkout_session.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def subscription_success(request):
    """Subscription success page"""
    messages.success(request, 'Subscription activated successfully!')
    return render(request, 'cinemai/subscription_success.html')


@csrf_exempt
def stripe_webhook(request):
    """Handle Stripe webhooks"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError:
        return JsonResponse({'error': 'Invalid signature'}, status=400)
    
    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session.get('client_reference_id')
        tier = session.get('metadata', {}).get('tier')
        
        if user_id:
            try:
                from django.contrib.auth.models import User
                user = User.objects.get(id=user_id)
                profile = user.profile
                profile.subscription_tier = tier
                profile.subscription_active = True
                profile.stripe_customer_id = session.get('customer')
                profile.stripe_subscription_id = session.get('subscription')
                profile.save()
            except User.DoesNotExist:
                pass
    
    return JsonResponse({'status': 'success'})


class CustomPasswordResetView(PasswordResetView):
    """Custom password reset view"""
    template_name = 'cinemai/password_reset.html'
    email_template_name = 'cinemai/password_reset_email.html'
    success_url = reverse_lazy('password_reset_done')


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """Custom password reset confirm view"""
    template_name = 'cinemai/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')