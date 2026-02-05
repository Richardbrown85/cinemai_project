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


@login_required
def search_movies(request):
    """AI-powered movie search view"""
    movies = []
    search_query = ''
    
    if request.method == 'POST':
        search_query = request.POST.get('search_query', '')
        genre = request.POST.get('genre', '')
        
        # Save search history
        SearchHistory.objects.create(
            user=request.user,
            query=search_query,
            genre=genre
        )
        
        # Use OpenAI to get movie recommendations
        if client and search_query:
            try:
                prompt = f"Recommend 10 movies based on: {search_query}"
                if genre:
                    prompt += f" in the {genre} genre"
                prompt += ". Return only movie titles, one per line."
                
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a movie recommendation assistant."},
                        {"role": "user", "content": prompt}
                    ]
                )
                
                movie_titles = response.choices[0].message.content.strip().split('\n')
                
                # Fetch movie details from OMDB or store as basic entries
                for title in movie_titles:
                    title = title.strip('0123456789. ')
                    if title:
                        # Try to get or create movie
                        movie, created = Movie.objects.get_or_create(
                            title=title,
                            defaults={'genre': genre}
                        )
                        movies.append(movie)
                        
            except Exception as e:
                messages.error(request, f'Error getting recommendations: {str(e)}')
        else:
            # Fallback: search existing movies
            movies = Movie.objects.filter(title__icontains=search_query)
            if genre:
                movies = movies.filter(genre__icontains=genre)
    
    context = {
        'movies': movies,
        'search_query': search_query,
    }
    return render(request, 'cinemai/search.html', context)


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
        'basic_price': 999,  # in cents
        'standard_price': 1499,
        'pro_price': 1999,
    }
    return render(request, 'cinemaisubscription.html', context)


@login_required
def create_checkout_session(request):
    """Create Stripe checkout session"""
    if request.method == 'POST':
        data = json.loads(request.body)
        tier = data.get('tier')
        
        price_map = {
            'BASIC': 999,
            'STANDARD': 1499,
            'PRO': 1999,
        }
        
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': f'CinemAI {tier.capitalize()} Subscription',
                        },
                        'unit_amount': price_map.get(tier, 999),
                        'recurring': {
                            'interval': 'month',
                        },
                    },
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=request.build_absolute_uri('/subscription/success/'),
                cancel_url=request.build_absolute_uri('/subscription/'),
                client_reference_id=str(request.user.id),
                metadata={
                    'tier': tier,
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