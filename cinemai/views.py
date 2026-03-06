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

# OpenAI client - lazy initialization
client = None

def get_openai_client():
    """Lazy load OpenAI client"""
    global client
    if client is None and settings.OPENAI_API_KEY:
        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
        except Exception as e:
            print(f"OpenAI initialization failed: {e}")
            client = None
    return client

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def home(request):
    """Home page view"""
    context = {
        'user': request.user,
    }
    return render(request, 'cinemai/home.html', context)


def signup_view(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('search')
    
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
        return redirect('search')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                next_url = request.GET.get('next', 'search')
                return redirect(next_url)
    else:
        form = LoginForm()
    
    return render(request, 'cinemai/login.html', {'form': form})


@login_required
def logout_view(request):
    """User logout view"""
    logout(request)
    return redirect('home')


@login_required
def account_view(request):
    """User account management view"""
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        
        if user_form.is_valid():
            user_form.save()
            messages.success(request, 'Your account has been updated!')
            return redirect('account')
    else:
        user_form = UserUpdateForm(instance=request.user)
    
    context = {
        'user_form': user_form,
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
    
    # Helper function to sort movies by relevance
    def sort_movies_by_relevance(movies_list, query):
        """Sort movies: exact match > starts with > contains > popularity"""
        def sort_key(movie):
            query_lower = query.lower()
            title_lower = movie.title.lower()
            
            # Exact match gets highest priority
            if query_lower == title_lower:
                return (0, -movie.popularity if movie.popularity else 0)
            # Title starts with query
            elif title_lower.startswith(query_lower):
                return (1, -movie.popularity if movie.popularity else 0)
            # Query in title
            elif query_lower in title_lower:
                return (2, -movie.popularity if movie.popularity else 0)
            # No match
            else:
                return (3, -movie.popularity if movie.popularity else 0)
        
        return sorted(movies_list, key=sort_key)
    
    if request.method == 'POST':
        search_query = request.POST.get('search_query', '')
        genre = request.POST.get('genre', '')
        
        # Check search limits for authenticated users
        if request.user.is_authenticated:
            from .models import SearchLog
            can_search, remaining = SearchLog.can_search(request.user)
            
            if not can_search:
                messages.error(request, 'You have reached your daily search limit of 10 searches. Upgrade to Standard for unlimited searches!')
                return render(request, 'cinemai/search.html', {
                    'search_limit_reached': True,
                    'user_tier': request.user.profile.subscription_tier,
                })
            
            # Log the search
            SearchLog.objects.create(user=request.user, search_query=search_query)
            
            # Save search history
            SearchHistory.objects.create(
                user=request.user,
                query=search_query,
                genre=genre
            )
        else:
            # Redirect to signup - no guest searches allowed
            messages.info(request, 'Create a free account to start searching for movies!')
            return redirect('signup')
        
        if search_query:
            try:
                from .tmdb_service import TMDBService
                tmdb = TMDBService()
                
                # Check if OpenAI is available for smart search
                client = get_openai_client()
                if client:
                    
                    # Use OpenAI to understand the query and suggest movies
                    try:
                        prompt = f"""Based on this search query: "{search_query}"

If this appears to be a specific movie title, include that exact movie FIRST in your list.
Then suggest 7-9 additional movies that match this request.

For EACH movie, provide:
1. The movie title
2. A brief reason why it matches (one sentence, 15-20 words max)

Format your response EXACTLY like this:
Movie Title | Reason why it matches the search

Example:
Inception | Mind-bending sci-fi thriller exploring dreams within dreams with stunning visuals
The Matrix | Revolutionary action film questioning reality with groundbreaking special effects

Return 8-10 movies in this format, no numbering, no extra text."""

                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {"role": "system", "content": "You are a movie recommendation expert. Provide accurate, specific movie titles with brief explanations."},
                                {"role": "user", "content": prompt}
                            ],
                            max_tokens=300,
                            temperature=0.7
                        )
                        
                        movie_lines = response.choices[0].message.content.strip().split('\n')
                        
                        # Parse movie title and reasoning
                        movie_recommendations = []
                        for line in movie_lines[:10]:
                            if '|' in line:
                                parts = line.split('|', 1)
                                title = parts[0].strip('0123456789. -•').strip()
                                reasoning = parts[1].strip() if len(parts) > 1 else None
                                if title:
                                    movie_recommendations.append({
                                        'title': title,
                                        'reasoning': reasoning
                                    })
                        
                        # Search TMDB for each suggested movie
                        for recommendation in movie_recommendations:
                            title = recommendation['title']
                            reasoning = recommendation['reasoning']
                            
                            if title:
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
                                    
                                    # Attach AI reasoning temporarily (not saved to DB)
                                    movie.ai_reasoning = reasoning
                                    
                                    movies.append(movie)
                        
                        # Sort results by relevance
                        movies = sort_movies_by_relevance(movies, search_query)
                    
                    except Exception as openai_error:
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
                        
                        # Sort results by relevance
                        movies = sort_movies_by_relevance(movies, search_query)
                
                else:
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
                    
                    # Sort results by relevance
                    movies = sort_movies_by_relevance(movies, search_query)
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                messages.error(request, f'Error searching movies: {str(e)}')
        
        # Apply Advanced Filters (Standard users only)
        if request.user.is_authenticated and request.user.profile.subscription_tier == 'STANDARD':
            year_min = request.POST.get('year_min', '')
            year_max = request.POST.get('year_max', '')
            min_rating = request.POST.get('min_rating', '')
            
            # Filter by year range
            if year_min:
                try:
                    year_min_int = int(year_min)
                    movies = [m for m in movies if m.year and m.year >= year_min_int]
                except ValueError:
                    pass
            
            if year_max:
                try:
                    year_max_int = int(year_max)
                    movies = [m for m in movies if m.year and m.year <= year_max_int]
                except ValueError:
                    pass
            
            # Filter by minimum rating
            if min_rating:
                try:
                    min_rating_float = float(min_rating)
                    movies = [m for m in movies if m.rating and m.rating >= min_rating_float]
                except ValueError:
                    pass
    
    context = {
        'movies': movies,
        'search_query': search_query,
        'year_min': request.POST.get('year_min', '') if request.method == 'POST' else '',
        'year_max': request.POST.get('year_max', '') if request.method == 'POST' else '',
        'min_rating': request.POST.get('min_rating', '') if request.method == 'POST' else '',
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
        # Get poster URL with fallback for missing posters
        poster_url = tmdb.get_poster_url(similar_data.get('poster_path'))
        if not poster_url:
            poster_url = 'https://via.placeholder.com/500x750?text=No+Poster'
        
        similar_movie, created = Movie.objects.get_or_create(
            tmdb_id=similar_data.get('id'),
            defaults={
                'title': similar_data.get('title', ''),
                'year': int(similar_data.get('release_date', '0000')[:4]) if similar_data.get('release_date') else None,
                'plot': similar_data.get('overview', ''),
                'poster_url': poster_url,
                'backdrop_url': tmdb.get_backdrop_url(similar_data.get('backdrop_path')),
                'rating': similar_data.get('vote_average'),
                'popularity': similar_data.get('popularity'),
                'vote_count': similar_data.get('vote_count'),
            }
        )
        similar_movies.append(similar_movie)
    
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
def cancel_subscription(request):
    """Cancel user's active subscription"""
    if request.method == 'POST':
        profile = request.user.profile
        
        # Check if user has an active subscription
        if not profile.stripe_subscription_id:
            messages.error(request, 'No active subscription found.')
            return redirect('account')
        
        try:
            # Cancel the subscription in Stripe
            stripe.Subscription.delete(profile.stripe_subscription_id)
            
            # Update user profile
            profile.subscription_tier = 'BASIC'
            profile.subscription_active = False
            profile.stripe_subscription_id = None
            profile.save()
            
            messages.success(request, 'Your subscription has been cancelled successfully. You now have a Basic (Free) plan.')
            
        except stripe.error.StripeError as e:
            messages.error(request, f'Error cancelling subscription: {str(e)}')
        
        return redirect('account')
    
    # If not POST, redirect to account
    return redirect('account')


@login_required
def create_checkout_session(request):
    """Create Stripe checkout session"""
    if request.method == 'POST':
        data = json.loads(request.body)
        tier = data.get('tier')
        
        # Stripe Price IDs (GBP)
        price_map = {
            'STANDARD': 'price_1T1qc7Iux0tpDCVobkSiqu2K',  # £9.99/month
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
                success_url=request.build_absolute_uri(f'/subscription/success/?tier={tier}'),
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
    # For local development: update subscription tier from URL parameter
    tier = request.GET.get('tier', 'STANDARD').upper()
    
    if tier in ['STANDARD', 'BASIC']:
        profile = request.user.profile
        profile.subscription_tier = tier
        profile.subscription_active = True
        profile.save()
        
        messages.success(request, f'{tier.title()} subscription activated successfully!')
    else:
        messages.success(request, 'Subscription activated successfully!')
    
    return render(request, 'cinema/subscription_success.html')


@csrf_exempt
def stripe_webhook(request):
    """Handle Stripe webhooks"""
    import logging
    logger = logging.getLogger(__name__)
    
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Webhook ValueError: {e}")
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Webhook SignatureVerificationError: {e}")
        return JsonResponse({'error': 'Invalid signature'}, status=400)
    
    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session.get('client_reference_id')
        tier = session.get('metadata', {}).get('tier')
        
        if user_id:
            try:
                from django.contrib.auth.models import User
                from django.core.mail import send_mail
                from django.template.loader import render_to_string
                from datetime import datetime, timedelta
                
                user = User.objects.get(id=user_id)
                profile = user.profile
                profile.subscription_tier = tier
                profile.subscription_active = True
                profile.stripe_customer_id = session.get('customer')
                profile.stripe_subscription_id = session.get('subscription')
                profile.save()
                
                logger.info(f"Subscription updated for user {user.username}")
                
                # Send subscription success email
                try:
                    next_billing_date = (datetime.now() + timedelta(days=30)).strftime('%B %d, %Y')
                    context = {
                        'user': user,
                        'next_billing_date': next_billing_date,
                        'protocol': 'https',
                        'domain': request.get_host(),
                    }
                    
                    html_message = render_to_string('cinemai/subscription_success_email.html', context)
                    plain_message = render_to_string('cinemai/subscription_success_email.txt', context)
                    
                    send_mail(
                        subject='Welcome to CinemAI Standard Plan!',
                        message=plain_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        html_message=html_message,
                        fail_silently=False,
                    )
                    logger.info(f"Success email sent to {user.email}")
                except Exception as e:
                    logger.error(f"Error sending subscription email: {e}")
                    # Don't fail the webhook if email fails
                    
            except User.DoesNotExist:
                logger.error(f"User {user_id} not found")
            except Exception as e:
                logger.error(f"Error in checkout.session.completed handler: {e}")
                return JsonResponse({'error': str(e)}, status=500)
    
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        subscription_id = subscription['id']
        previous_attributes = event['data'].get('previous_attributes', {})
        
        # Only handle if subscription is being cancelled (not just created/updated)
        # Check if cancel_at_period_end changed from False to True
        if subscription.get('cancel_at_period_end') and not previous_attributes.get('cancel_at_period_end'):
            try:
                from django.contrib.auth.models import User
                from django.core.mail import send_mail
                from django.template.loader import render_to_string
                from datetime import datetime
                
                # Find user by subscription ID
                try:
                    profile = UserProfile.objects.get(stripe_subscription_id=subscription_id)
                except UserProfile.DoesNotExist:
                    logger.error(f"Profile with subscription {subscription_id} not found")
                    return JsonResponse({'status': 'success'})
                
                user = profile.user
                
                # Calculate access until date
                if subscription.get('current_period_end'):
                    profile.subscription_end_date = datetime.fromtimestamp(subscription['current_period_end'])
                    access_until_date = profile.subscription_end_date.strftime('%B %d, %Y')
                else:
                    access_until_date = datetime.now().strftime('%B %d, %Y')
                
                profile.save()
                logger.info(f"Subscription cancellation scheduled for user {user.username} until {access_until_date}")
                
                # Send cancellation email
                try:
                    context = {
                        'user': user,
                        'access_until_date': access_until_date,
                        'protocol': 'https',
                        'domain': request.get_host(),
                    }
                    
                    html_message = render_to_string('cinemai/subscription_cancelled_email.html', context)
                    plain_message = render_to_string('cinemai/subscription_cancelled_email.txt', context)
                    
                    send_mail(
                        subject='CinemAI Subscription Cancelled',
                        message=plain_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        html_message=html_message,
                        fail_silently=False,
                    )
                    logger.info(f"Cancellation email sent to {user.email}")
                except Exception as e:
                    logger.error(f"Error sending cancellation email: {e}")
                    
            except Exception as e:
                logger.error(f"Error in customer.subscription.updated handler: {e}")
    
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        subscription_id = subscription['id']
        
        try:
            from django.contrib.auth.models import User
            from django.core.mail import send_mail
            from django.template.loader import render_to_string
            from datetime import datetime
            
            # Find user by subscription ID
            profile = UserProfile.objects.get(stripe_subscription_id=subscription_id)
            user = profile.user
            
            # Update profile
            profile.subscription_tier = 'BASIC'
            profile.subscription_active = False
            profile.subscription_end_date = datetime.now()
            profile.save()
            
            logger.info(f"Subscription cancelled for user {user.username}")
            
            # Send cancellation email
            try:
                access_until_date = datetime.now().strftime('%B %d, %Y')
                context = {
                    'user': user,
                    'access_until_date': access_until_date,
                    'protocol': 'https',
                    'domain': request.get_host(),
                }
                
                html_message = render_to_string('cinemai/subscription_cancelled_email.html', context)
                plain_message = render_to_string('cinemai/subscription_cancelled_email.txt', context)
                
                send_mail(
                    subject='CinemAI Subscription Cancelled',
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                logger.info(f"Cancellation email sent to {user.email}")
            except Exception as e:
                logger.error(f"Error sending cancellation email: {e}")
                
        except UserProfile.DoesNotExist:
            logger.error(f"Profile with subscription {subscription_id} not found")
        except Exception as e:
            logger.error(f"Error in customer.subscription.deleted handler: {e}")
    
    return JsonResponse({'status': 'success'})




class CustomPasswordResetView(PasswordResetView):
    """Custom password reset view"""
    template_name = 'cinemai/password_reset.html'
    email_template_name = 'cinemai/password_reset_email.html'
    html_email_template_name = 'cinemai/password_reset_email.html'
    subject_template_name = 'cinemai/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """Custom password reset confirm view"""
    template_name = 'cinemai/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')


def custom_404(request, exception):
    """Custom 404 error page"""
    return render(request, 'cinemai/404.html', status=404)