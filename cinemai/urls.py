from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Home
    path('', views.home, name='home'),
    
    # Authentication
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Password Reset
    path('password-reset/', 
         views.CustomPasswordResetView.as_view(), 
         name='password_reset'),
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(template_name='cinemai/password_reset_done.html'), 
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', 
         views.CustomPasswordResetConfirmView.as_view(), 
         name='password_reset_confirm'),
    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(template_name='cinemai/password_reset_complete.html'), 
         name='password_reset_complete'),
    
    # Account Management
    path('account/', views.account_view, name='account'),
    path('account/delete/', views.delete_account, name='delete_account'),
    
    # Movie Search
    path('search/', views.search_movies, name='search'),
    
    # Watchlist
    path('watchlist/', views.watchlist_view, name='watchlist'),
    path('watchlist/add/<int:movie_id>/', views.add_to_watchlist, name='add_to_watchlist'),
    path('watchlist/remove/<int:watchlist_id>/', views.remove_from_watchlist, name='remove_from_watchlist'),
    path('watchlist/update/<int:watchlist_id>/', views.update_watchlist_item, name='update_watchlist'),
    
    # Subscription
    path('subscription/', views.subscription_view, name='subscription'),
    path('subscription/create-checkout-session/', views.create_checkout_session, name='create_checkout_session'),
    path('subscription/success/', views.subscription_success, name='subscription_success'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
]