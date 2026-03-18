"""
CinemAI Model Tests
Tests for all models: UserProfile, SearchLog, Movie, Watchlist, SearchHistory
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from cinemai.models import (
    UserProfile, 
    SearchLog, 
    Movie, 
    Watchlist, 
    SearchHistory,
    SubscriptionTier
)


class UserProfileModelTest(TestCase):
    """Test cases for UserProfile model"""
    
    def setUp(self):
        """Create test user for profile tests"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_profile_created_automatically(self):
        """Test that UserProfile is created automatically when User is created"""
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertIsInstance(self.user.profile, UserProfile)
    
    def test_default_subscription_tier(self):
        """Test that new users default to BASIC tier"""
        self.assertEqual(self.user.profile.subscription_tier, SubscriptionTier.BASIC)
    
    def test_profile_str_method(self):
        """Test UserProfile string representation"""
        expected = f"{self.user.username} - {self.user.profile.subscription_tier}"
        self.assertEqual(str(self.user.profile), expected)
    
    def test_tier_price_basic(self):
        """Test tier_price property for BASIC tier"""
        self.user.profile.subscription_tier = SubscriptionTier.BASIC
        self.assertEqual(self.user.profile.tier_price, 0.00)
    
    def test_tier_price_standard(self):
        """Test tier_price property for STANDARD tier"""
        self.user.profile.subscription_tier = SubscriptionTier.STANDARD
        self.assertEqual(self.user.profile.tier_price, 9.99)
    
    def test_subscription_active_default(self):
        """Test that subscription_active defaults to False"""
        self.assertFalse(self.user.profile.subscription_active)
    
    def test_stripe_fields_default_to_none(self):
        """Test that Stripe fields are initially None"""
        self.assertIsNone(self.user.profile.stripe_customer_id)
        self.assertIsNone(self.user.profile.stripe_subscription_id)
    
    def test_subscription_upgrade(self):
        """Test upgrading subscription from BASIC to STANDARD"""
        self.user.profile.subscription_tier = SubscriptionTier.STANDARD
        self.user.profile.subscription_active = True
        self.user.profile.save()
        
        # Reload from database
        self.user.profile.refresh_from_db()
        
        self.assertEqual(self.user.profile.subscription_tier, SubscriptionTier.STANDARD)
        self.assertTrue(self.user.profile.subscription_active)


class SearchLogModelTest(TestCase):
    """Test cases for SearchLog model"""
    
    def setUp(self):
        """Create test user and search logs"""
        self.user = User.objects.create_user(
            username='searchuser',
            password='testpass123'
        )
        self.today = timezone.now().date()
    
    def test_search_log_creation(self):
        """Test creating a search log entry"""
        search_log = SearchLog.objects.create(
            user=self.user,
            search_query='action movies'
        )
        self.assertEqual(search_log.search_query, 'action movies')
        self.assertEqual(search_log.user, self.user)
    
    def test_search_log_str_method(self):
        """Test SearchLog string representation"""
        search_log = SearchLog.objects.create(
            user=self.user,
            search_query='comedy'
        )
        expected = f"{self.user.username} - comedy ({self.today})"
        self.assertEqual(str(search_log), expected)
    
    def test_get_daily_search_count(self):
        """Test getting daily search count for a user"""
        # Create 5 searches today
        for i in range(5):
            SearchLog.objects.create(
                user=self.user,
                search_query=f'query {i}'
            )
        
        count = SearchLog.get_daily_search_count(self.user)
        self.assertEqual(count, 5)
    
    def test_get_daily_search_count_different_dates(self):
        """Test that searches from different dates don't count"""
        # Create searches today
        SearchLog.objects.create(user=self.user, search_query='today query')
        
        # Create search from yesterday (manually set)
        yesterday_search = SearchLog.objects.create(
            user=self.user,
            search_query='yesterday query'
        )
        yesterday_search.search_date = self.today - timedelta(days=1)
        yesterday_search.save()
        
        count = SearchLog.get_daily_search_count(self.user, self.today)
        self.assertEqual(count, 1)  # Only today's search
    
    def test_can_search_basic_user_under_limit(self):
        """Test that BASIC user under 10 searches can search"""
        # Create 5 searches
        for i in range(5):
            SearchLog.objects.create(user=self.user, search_query=f'query {i}')
        
        can_search, remaining = SearchLog.can_search(self.user)
        self.assertTrue(can_search)
        self.assertEqual(remaining, 5)  # 10 - 5 = 5 remaining
    
    def test_can_search_basic_user_at_limit(self):
        """Test that BASIC user at 10 searches cannot search"""
        # Create 10 searches
        for i in range(10):
            SearchLog.objects.create(user=self.user, search_query=f'query {i}')
        
        can_search, remaining = SearchLog.can_search(self.user)
        self.assertFalse(can_search)
        self.assertEqual(remaining, 0)
    
    def test_can_search_standard_user_unlimited(self):
        """Test that STANDARD user has unlimited searches"""
        self.user.profile.subscription_tier = SubscriptionTier.STANDARD
        self.user.profile.save()
        
        # Create 15 searches (over basic limit)
        for i in range(15):
            SearchLog.objects.create(user=self.user, search_query=f'query {i}')
        
        can_search, remaining = SearchLog.can_search(self.user)
        self.assertTrue(can_search)
        self.assertEqual(remaining, 0)  # 0 means unlimited


class MovieModelTest(TestCase):
    """Test cases for Movie model"""
    
    def test_movie_creation(self):
        """Test creating a movie with basic fields"""
        movie = Movie.objects.create(
            title='The Matrix',
            year=1999,
            genre='Sci-Fi, Action',
            tmdb_id=603
        )
        self.assertEqual(movie.title, 'The Matrix')
        self.assertEqual(movie.year, 1999)
        self.assertEqual(movie.tmdb_id, 603)
    
    def test_movie_str_method(self):
        """Test Movie string representation"""
        movie = Movie.objects.create(
            title='Inception',
            year=2010
        )
        self.assertEqual(str(movie), 'Inception (2010)')
    
    def test_movie_str_method_no_year(self):
        """Test Movie string representation without year"""
        movie = Movie.objects.create(title='Unknown Movie')
        self.assertEqual(str(movie), 'Unknown Movie (None)')
    
    def test_genre_list_property(self):
        """Test genre_list property splits genres correctly"""
        movie = Movie.objects.create(
            title='Test Movie',
            genre='Action, Comedy, Drama'
        )
        expected = ['Action', 'Comedy', 'Drama']
        self.assertEqual(movie.genre_list, expected)
    
    def test_genre_list_property_single_genre(self):
        """Test genre_list with single genre"""
        movie = Movie.objects.create(
            title='Test Movie',
            genre='Horror'
        )
        self.assertEqual(movie.genre_list, ['Horror'])
    
    def test_genre_list_property_empty(self):
        """Test genre_list with no genre"""
        movie = Movie.objects.create(title='Test Movie')
        self.assertEqual(movie.genre_list, [])
    
    def test_movie_with_all_fields(self):
        """Test creating movie with all optional fields"""
        movie = Movie.objects.create(
            title='The Dark Knight',
            year=2008,
            genre='Action, Crime, Drama',
            director='Christopher Nolan',
            plot='Batman faces the Joker',
            poster_url='https://example.com/poster.jpg',
            backdrop_url='https://example.com/backdrop.jpg',
            tmdb_id=155,
            imdb_id='tt0468569',
            rating=Decimal('9.0'),
            runtime=152,
            popularity=100.5,
            vote_count=25000,
            trailer_url='https://youtube.com/watch?v=abc',
            streaming_providers={'Netflix': True, 'Prime': False}
        )
        
        self.assertEqual(movie.director, 'Christopher Nolan')
        self.assertEqual(movie.rating, Decimal('9.0'))
        self.assertEqual(movie.runtime, 152)
        self.assertIn('Netflix', movie.streaming_providers)
    
    def test_tmdb_id_unique(self):
        """Test that tmdb_id must be unique"""
        Movie.objects.create(title='Movie 1', tmdb_id=123)
        
        with self.assertRaises(Exception):  # IntegrityError
            Movie.objects.create(title='Movie 2', tmdb_id=123)
    
    def test_streaming_providers_default(self):
        """Test that streaming_providers defaults to empty dict"""
        movie = Movie.objects.create(title='Test Movie')
        self.assertEqual(movie.streaming_providers, {})


class WatchlistModelTest(TestCase):
    """Test cases for Watchlist model"""
    
    def setUp(self):
        """Create test user and movie for watchlist tests"""
        self.user = User.objects.create_user(
            username='watchlistuser',
            password='testpass123'
        )
        self.movie = Movie.objects.create(
            title='Inception',
            year=2010,
            tmdb_id=27205
        )
    
    def test_watchlist_creation(self):
        """Test adding movie to watchlist"""
        watchlist_item = Watchlist.objects.create(
            user=self.user,
            movie=self.movie
        )
        self.assertEqual(watchlist_item.user, self.user)
        self.assertEqual(watchlist_item.movie, self.movie)
        self.assertFalse(watchlist_item.watched)
    
    def test_watchlist_str_method(self):
        """Test Watchlist string representation"""
        watchlist_item = Watchlist.objects.create(
            user=self.user,
            movie=self.movie
        )
        expected = f"{self.user.username} - {self.movie.title}"
        self.assertEqual(str(watchlist_item), expected)
    
    def test_watchlist_watched_default(self):
        """Test that watched defaults to False"""
        watchlist_item = Watchlist.objects.create(
            user=self.user,
            movie=self.movie
        )
        self.assertFalse(watchlist_item.watched)
    
    def test_watchlist_mark_as_watched(self):
        """Test marking movie as watched"""
        watchlist_item = Watchlist.objects.create(
            user=self.user,
            movie=self.movie
        )
        watchlist_item.watched = True
        watchlist_item.save()
        
        watchlist_item.refresh_from_db()
        self.assertTrue(watchlist_item.watched)
    
    def test_watchlist_with_notes(self):
        """Test adding notes to watchlist item"""
        watchlist_item = Watchlist.objects.create(
            user=self.user,
            movie=self.movie,
            notes='Want to watch this weekend'
        )
        self.assertEqual(watchlist_item.notes, 'Want to watch this weekend')
    
    def test_watchlist_unique_together(self):
        """Test that user cannot add same movie twice"""
        Watchlist.objects.create(user=self.user, movie=self.movie)
        
        with self.assertRaises(Exception):  # IntegrityError
            Watchlist.objects.create(user=self.user, movie=self.movie)
    
    def test_multiple_users_same_movie(self):
        """Test that different users can add same movie"""
        user2 = User.objects.create_user(username='user2', password='pass123')
        
        watchlist1 = Watchlist.objects.create(user=self.user, movie=self.movie)
        watchlist2 = Watchlist.objects.create(user=user2, movie=self.movie)
        
        self.assertEqual(Watchlist.objects.filter(movie=self.movie).count(), 2)


class SearchHistoryModelTest(TestCase):
    """Test cases for SearchHistory model"""
    
    def setUp(self):
        """Create test user for search history tests"""
        self.user = User.objects.create_user(
            username='historyuser',
            password='testpass123'
        )
    
    def test_search_history_creation(self):
        """Test creating search history entry"""
        history = SearchHistory.objects.create(
            user=self.user,
            query='action movies'
        )
        self.assertEqual(history.query, 'action movies')
        self.assertEqual(history.user, self.user)
    
    def test_search_history_str_method(self):
        """Test SearchHistory string representation"""
        history = SearchHistory.objects.create(
            user=self.user,
            query='comedy films'
        )
        expected = f"{self.user.username} - comedy films"
        self.assertEqual(str(history), expected)
    
    def test_search_history_with_genre(self):
        """Test search history with genre filter"""
        history = SearchHistory.objects.create(
            user=self.user,
            query='scary movies',
            genre='Horror'
        )
        self.assertEqual(history.genre, 'Horror')
    
    def test_search_history_ordering(self):
        """Test that search history is ordered by most recent"""
        history1 = SearchHistory.objects.create(user=self.user, query='first')
        history2 = SearchHistory.objects.create(user=self.user, query='second')
        history3 = SearchHistory.objects.create(user=self.user, query='third')
        
        histories = list(SearchHistory.objects.filter(user=self.user))
        
        # Most recent should be first
        self.assertEqual(histories[0], history3)
        self.assertEqual(histories[1], history2)
        self.assertEqual(histories[2], history1)
    
    def test_multiple_users_search_histories(self):
        """Test that search histories are user-specific"""
        user2 = User.objects.create_user(username='user2', password='pass123')
        
        SearchHistory.objects.create(user=self.user, query='user1 query')
        SearchHistory.objects.create(user=user2, query='user2 query')
        
        user1_history = SearchHistory.objects.filter(user=self.user)
        user2_history = SearchHistory.objects.filter(user=user2)
        
        self.assertEqual(user1_history.count(), 1)
        self.assertEqual(user2_history.count(), 1)