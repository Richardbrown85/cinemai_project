"""
CinemAI View Tests
Tests for all views: authentication, search, watchlist, movie detail, subscriptions
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from decimal import Decimal

from cinemai.models import (
    Movie, 
    Watchlist, 
    SearchHistory, 
    SearchLog, 
    UserProfile,
    SubscriptionTier
)


class AuthenticationViewTests(TestCase):
    """Test cases for authentication views (signup, login, logout)"""
    
    def setUp(self):
        """Set up test client and user"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_home_view_get(self):
        """Test home page loads successfully"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cinemai/home.html')
    
    def test_signup_view_get(self):
        """Test signup page loads for anonymous users"""
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cinemai/signup.html')
    
    def test_signup_view_authenticated_redirect(self):
        """Test authenticated users are redirected from signup"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('signup'))
        self.assertRedirects(response, reverse('search'))
    
    def test_signup_creates_user(self):
        """Test user creation through signup form"""
        response = self.client.post(reverse('signup'), {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'complexpass123',
            'password2': 'complexpass123',
        })
        
        # Should redirect to login after successful signup
        self.assertRedirects(response, reverse('login'))
        
        # User should exist
        self.assertTrue(User.objects.filter(username='newuser').exists())
        
        # Profile should be created automatically
        new_user = User.objects.get(username='newuser')
        self.assertTrue(hasattr(new_user, 'profile'))
    
    def test_login_view_get(self):
        """Test login page loads for anonymous users"""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cinemai/login.html')
    
    def test_login_view_authenticated_redirect(self):
        """Test authenticated users are redirected from login"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('search'))
    
    def test_login_successful(self):
        """Test successful login"""
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123',
        })
        
        # Should redirect to search after successful login
        self.assertRedirects(response, reverse('search'))
        
        # User should be authenticated
        self.assertTrue(response.wsgi_request.user.is_authenticated)
    
    def test_login_with_next_parameter(self):
        """Test login redirects to next parameter"""
        response = self.client.post(
            reverse('login') + '?next=/watchlist/',
            {
                'username': 'testuser',
                'password': 'testpass123',
            }
        )
        self.assertRedirects(response, '/watchlist/')
    
    def test_logout_view(self):
        """Test logout functionality"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('logout'))
        
        # Should redirect to home
        self.assertRedirects(response, reverse('home'))
        
        # Check that user is logged out by trying to access account page
        response = self.client.get(reverse('account'))
        self.assertEqual(response.status_code, 302)  # Redirects to login
    
    def test_logout_requires_authentication(self):
        """Test logout requires authentication"""
        response = self.client.get(reverse('logout'))
        # Should redirect to login with next parameter
        self.assertEqual(response.status_code, 302)


class AccountViewTests(TestCase):
    """Test cases for account management views"""
    
    def setUp(self):
        """Set up test client and user"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_account_view_requires_login(self):
        """Test account view requires authentication"""
        self.client.logout()
        response = self.client.get(reverse('account'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_account_view_get(self):
        """Test account page loads for authenticated users"""
        response = self.client.get(reverse('account'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cinemai/account.html')
    
    def test_account_update_email(self):
        """Test updating user email"""
        response = self.client.post(reverse('account'), {
            'username': 'testuser',
            'email': 'newemail@example.com',
        })
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'newemail@example.com')
    
    def test_delete_account_view_get(self):
        """Test delete account confirmation page"""
        response = self.client.get(reverse('delete_account'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cinemai/delete_account.html')
    
    def test_delete_account_post(self):
        """Test account deletion"""
        user_id = self.user.id
        response = self.client.post(reverse('delete_account'))
        
        # Should redirect to home
        self.assertRedirects(response, reverse('home'))
        
        # User should be deleted
        self.assertFalse(User.objects.filter(id=user_id).exists())


class SearchViewTests(TestCase):
    """Test cases for movie search functionality"""
    
    def setUp(self):
        """Set up test client, user, and mock TMDB"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='searchuser',
            password='testpass123'
        )
        self.client.login(username='searchuser', password='testpass123')
    
    def test_search_view_get(self):
        """Test search page loads"""
        response = self.client.get(reverse('search'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cinemai/search.html')
    
    def test_search_requires_authentication(self):
        """Test unauthenticated users are redirected to signup"""
        self.client.logout()
        response = self.client.post(reverse('search'), {
            'search_query': 'Inception'
        })
        self.assertRedirects(response, reverse('signup'))
    
    @patch('cinemai.tmdb_service.TMDBService')
    def test_search_creates_search_log(self, mock_tmdb):
        """Test that search creates a search log entry"""
        # Mock TMDB service
        mock_tmdb_instance = mock_tmdb.return_value
        mock_tmdb_instance.search_movies.return_value = {'results': []}
        
        response = self.client.post(reverse('search'), {
            'search_query': 'Test Movie'
        })
        
        # Check search log was created
        self.assertEqual(SearchLog.objects.filter(user=self.user).count(), 1)
        search_log = SearchLog.objects.get(user=self.user)
        self.assertEqual(search_log.search_query, 'Test Movie')
    
    @patch('cinemai.tmdb_service.TMDBService')
    def test_search_creates_search_history(self, mock_tmdb):
        """Test that search creates a search history entry"""
        mock_tmdb_instance = mock_tmdb.return_value
        mock_tmdb_instance.search_movies.return_value = {'results': []}
        
        response = self.client.post(reverse('search'), {
            'search_query': 'Action Movies',
            'genre': 'Action'
        })
        
        # Check search history was created
        self.assertEqual(SearchHistory.objects.filter(user=self.user).count(), 1)
        history = SearchHistory.objects.get(user=self.user)
        self.assertEqual(history.query, 'Action Movies')
        self.assertEqual(history.genre, 'Action')
    
    @patch('cinemai.tmdb_service.TMDBService')
    def test_search_limit_basic_user(self, mock_tmdb):
        """Test that basic users hit search limit at 10 searches"""
        mock_tmdb_instance = mock_tmdb.return_value
        mock_tmdb_instance.search_movies.return_value = {'results': []}
        
        # Create 10 searches
        for i in range(10):
            SearchLog.objects.create(
                user=self.user,
                search_query=f'query {i}'
            )
        
        # 11th search should be blocked
        response = self.client.post(reverse('search'), {
            'search_query': 'blocked query'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('search_limit_reached', response.context)
        self.assertTrue(response.context['search_limit_reached'])
    
    @patch('cinemai.tmdb_service.TMDBService')
    def test_search_unlimited_standard_user(self, mock_tmdb):
        """Test that standard users have unlimited searches"""
        # Upgrade to standard
        self.user.profile.subscription_tier = SubscriptionTier.STANDARD
        self.user.profile.save()
        
        mock_tmdb_instance = mock_tmdb.return_value
        mock_tmdb_instance.search_movies.return_value = {'results': []}
        
        # Create 15 searches (over basic limit)
        for i in range(15):
            SearchLog.objects.create(
                user=self.user,
                search_query=f'query {i}'
            )
        
        # Should still be able to search
        response = self.client.post(reverse('search'), {
            'search_query': 'unlimited query'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('search_limit_reached', response.context)


class MovieDetailViewTests(TestCase):
    """Test cases for movie detail view"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='movieuser',
            password='testpass123'
        )
        self.movie = Movie.objects.create(
            title='Test Movie',
            year=2020,
            tmdb_id=12345,
            rating=Decimal('8.5')
        )
    
    @patch('cinemai.tmdb_service.TMDBService')
    def test_movie_detail_view(self, mock_tmdb):
        """Test movie detail page loads"""
        mock_tmdb_instance = mock_tmdb.return_value
        mock_tmdb_instance.get_movie_details.return_value = {
            'genres': [{'name': 'Action'}],
            'credits': {'cast': []}
        }
        mock_tmdb_instance.get_similar_movies.return_value = {'results': []}
        
        response = self.client.get(
            reverse('movie_detail', kwargs={'movie_id': self.movie.id})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cinemai/movie_detail.html')
        self.assertEqual(response.context['movie'], self.movie)
    
    @patch('cinemai.tmdb_service.TMDBService')
    def test_movie_detail_shows_watchlist_status(self, mock_tmdb):
        """Test movie detail shows if movie is in watchlist"""
        self.client.login(username='movieuser', password='testpass123')
        
        mock_tmdb_instance = mock_tmdb.return_value
        mock_tmdb_instance.get_movie_details.return_value = {'credits': {}}
        mock_tmdb_instance.get_similar_movies.return_value = {'results': []}
        
        # Add to watchlist
        Watchlist.objects.create(user=self.user, movie=self.movie)
        
        response = self.client.get(
            reverse('movie_detail', kwargs={'movie_id': self.movie.id})
        )
        
        self.assertTrue(response.context['in_watchlist'])
    
    def test_movie_detail_404(self):
        """Test movie detail returns 404 for non-existent movie"""
        response = self.client.get(
            reverse('movie_detail', kwargs={'movie_id': 99999})
        )
        self.assertEqual(response.status_code, 404)


class WatchlistViewTests(TestCase):
    """Test cases for watchlist functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='watchlistuser',
            password='testpass123'
        )
        self.client.login(username='watchlistuser', password='testpass123')
        
        self.movie1 = Movie.objects.create(
            title='Movie 1',
            year=2020,
            tmdb_id=111
        )
        self.movie2 = Movie.objects.create(
            title='Movie 2',
            year=2021,
            tmdb_id=222
        )
    
    def test_watchlist_view_requires_login(self):
        """Test watchlist requires authentication"""
        self.client.logout()
        response = self.client.get(reverse('watchlist'))
        self.assertEqual(response.status_code, 302)
    
    def test_watchlist_view_empty(self):
        """Test watchlist view with no items"""
        response = self.client.get(reverse('watchlist'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cinemai/watchlist.html')
        self.assertEqual(len(response.context['watchlist_items']), 0)
    
    def test_watchlist_view_with_items(self):
        """Test watchlist view displays items"""
        Watchlist.objects.create(user=self.user, movie=self.movie1)
        Watchlist.objects.create(user=self.user, movie=self.movie2, watched=True)
        
        response = self.client.get(reverse('watchlist'))
        
        self.assertEqual(len(response.context['watchlist_items']), 2)
        self.assertEqual(response.context['watched_count'], 1)
        self.assertEqual(response.context['to_watch_count'], 1)
    
    def test_add_to_watchlist(self):
        """Test adding movie to watchlist"""
        response = self.client.get(
            reverse('add_to_watchlist', kwargs={'movie_id': self.movie1.id})
        )
        
        # Should create watchlist item
        self.assertTrue(
            Watchlist.objects.filter(user=self.user, movie=self.movie1).exists()
        )
    
    def test_add_to_watchlist_duplicate(self):
        """Test adding same movie twice doesn't create duplicate"""
        # Add first time
        self.client.get(
            reverse('add_to_watchlist', kwargs={'movie_id': self.movie1.id})
        )
        
        # Add second time
        self.client.get(
            reverse('add_to_watchlist', kwargs={'movie_id': self.movie1.id})
        )
        
        # Should only have one entry
        self.assertEqual(
            Watchlist.objects.filter(user=self.user, movie=self.movie1).count(),
            1
        )
    
    def test_remove_from_watchlist(self):
        """Test removing movie from watchlist"""
        watchlist_item = Watchlist.objects.create(
            user=self.user,
            movie=self.movie1
        )
        
        response = self.client.get(
            reverse('remove_from_watchlist', kwargs={'watchlist_id': watchlist_item.id})
        )
        
        # Should redirect to watchlist
        self.assertRedirects(response, reverse('watchlist'))
        
        # Item should be deleted
        self.assertFalse(
            Watchlist.objects.filter(id=watchlist_item.id).exists()
        )
    
    def test_remove_from_watchlist_wrong_user(self):
        """Test user cannot remove another user's watchlist item"""
        other_user = User.objects.create_user(
            username='otheruser',
            password='testpass123'
        )
        watchlist_item = Watchlist.objects.create(
            user=other_user,
            movie=self.movie1
        )
        
        response = self.client.get(
            reverse('remove_from_watchlist', kwargs={'watchlist_id': watchlist_item.id})
        )
        
        # Should return 404
        self.assertEqual(response.status_code, 404)


class SubscriptionViewTests(TestCase):
    """Test cases for subscription views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='subuser',
            password='testpass123'
        )
        self.client.login(username='subuser', password='testpass123')
    
    def test_subscription_view_requires_login(self):
        """Test subscription view requires authentication"""
        self.client.logout()
        response = self.client.get(reverse('subscription'))
        self.assertEqual(response.status_code, 302)
    
    def test_subscription_view_get(self):
        """Test subscription page loads"""
        response = self.client.get(reverse('subscription'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cinemai/subscription.html')
    
    def test_subscription_success_view(self):
        """Test subscription success page"""
        response = self.client.get(reverse('subscription_success') + '?tier=STANDARD')
        
        self.assertEqual(response.status_code, 200)
        
        # User should be upgraded
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.subscription_tier, SubscriptionTier.STANDARD)
        self.assertTrue(self.user.profile.subscription_active)


class IntegrationTests(TestCase):
    """Integration tests for complete user workflows"""
    
    def test_complete_user_journey(self):
        """Test complete user journey: signup -> search -> watchlist"""
        # 1. Signup
        response = self.client.post(reverse('signup'), {
            'username': 'journeyuser',
            'email': 'journey@example.com',
            'password1': 'complexpass123',
            'password2': 'complexpass123',
        })
        self.assertRedirects(response, reverse('login'))
        
        # 2. Login
        response = self.client.post(reverse('login'), {
            'username': 'journeyuser',
            'password': 'complexpass123',
        })
        self.assertRedirects(response, reverse('search'))
        
        # 3. Create a movie and add to watchlist
        movie = Movie.objects.create(
            title='Journey Movie',
            year=2024,
            tmdb_id=789
        )
        
        response = self.client.get(
            reverse('add_to_watchlist', kwargs={'movie_id': movie.id})
        )
        
        # 4. Check watchlist
        response = self.client.get(reverse('watchlist'))
        self.assertEqual(len(response.context['watchlist_items']), 1)
        
        # 5. Logout
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('home'))