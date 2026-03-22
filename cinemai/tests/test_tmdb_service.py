"""
CinemAI TMDB Service Tests
Tests for TMDBService class - mocking all external API calls
"""

from django.test import TestCase, override_settings
from unittest.mock import patch, Mock
import requests

from cinemai.tmdb_service import TMDBService, get_genre_id, GENRE_MAP


@override_settings(
    TMDB_API_KEY='test_api_key',
    TMDB_BASE_URL='https://api.themoviedb.org/3',
    TMDB_IMAGE_BASE_URL='https://image.tmdb.org/t/p'
)
class TMDBServiceTests(TestCase):
    """Test cases for TMDBService class"""
    
    def setUp(self):
        """Set up TMDBService instance for testing"""
        self.service = TMDBService()
    
    def test_initialization(self):
        """Test TMDBService initializes with correct settings"""
        self.assertEqual(self.service.api_key, 'test_api_key')
        self.assertEqual(self.service.base_url, 'https://api.themoviedb.org/3')
        self.assertEqual(self.service.image_base_url, 'https://image.tmdb.org/t/p')
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_search_movies_success(self, mock_get):
        """Test successful movie search"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {'id': 27205, 'title': 'Inception', 'release_date': '2010-07-16'}
            ],
            'total_results': 1
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = self.service.search_movies('Inception')
        
        # Verify API was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertIn('query', call_args.kwargs['params'])
        self.assertEqual(call_args.kwargs['params']['query'], 'Inception')
        
        # Verify results
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['title'], 'Inception')
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_search_movies_with_pagination(self, mock_get):
        """Test movie search with page parameter"""
        mock_response = Mock()
        mock_response.json.return_value = {'results': [], 'total_results': 0}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        self.service.search_movies('Test', page=2)
        
        # Verify page parameter was passed
        call_args = mock_get.call_args
        self.assertEqual(call_args.kwargs['params']['page'], 2)
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_search_movies_api_error(self, mock_get):
        """Test movie search handles API errors gracefully"""
        # Mock API error
        mock_get.side_effect = requests.exceptions.RequestException('API Error')
        
        result = self.service.search_movies('Test')
        
        # Should return empty results, not raise exception
        self.assertEqual(result, {'results': [], 'total_results': 0})
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_get_movie_details_success(self, mock_get):
        """Test getting movie details"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'id': 27205,
            'title': 'Inception',
            'overview': 'A thief who steals corporate secrets...',
            'genres': [{'id': 28, 'name': 'Action'}],
            'credits': {'cast': []},
            'videos': {'results': []}
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = self.service.get_movie_details(27205)
        
        # Verify correct endpoint was called
        call_args = mock_get.call_args
        self.assertIn('/movie/27205', call_args.args[0])
        
        # Verify append_to_response parameter
        self.assertEqual(
            call_args.kwargs['params']['append_to_response'],
            'videos,credits,similar'
        )
        
        # Verify results
        self.assertEqual(result['title'], 'Inception')
        self.assertIn('credits', result)
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_get_movie_details_api_error(self, mock_get):
        """Test get movie details handles errors"""
        mock_get.side_effect = requests.exceptions.RequestException('API Error')
        
        result = self.service.get_movie_details(999999)
        
        # Should return None on error
        self.assertIsNone(result)
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_discover_movies_no_genre(self, mock_get):
        """Test discover movies without genre filter"""
        mock_response = Mock()
        mock_response.json.return_value = {'results': [], 'total_results': 0}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        self.service.discover_movies()
        
        # Verify parameters
        call_args = mock_get.call_args
        params = call_args.kwargs['params']
        self.assertEqual(params['sort_by'], 'popularity.desc')
        self.assertNotIn('with_genres', params)
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_discover_movies_with_genre(self, mock_get):
        """Test discover movies with genre filter"""
        mock_response = Mock()
        mock_response.json.return_value = {'results': [], 'total_results': 0}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        self.service.discover_movies(genre_id=28, sort_by='vote_average.desc')
        
        # Verify genre parameter
        call_args = mock_get.call_args
        params = call_args.kwargs['params']
        self.assertEqual(params['with_genres'], 28)
        self.assertEqual(params['sort_by'], 'vote_average.desc')
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_get_popular_movies(self, mock_get):
        """Test getting popular movies"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {'id': 1, 'title': 'Popular Movie 1'},
                {'id': 2, 'title': 'Popular Movie 2'}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = self.service.get_popular_movies(page=1)
        
        # Verify endpoint
        call_args = mock_get.call_args
        self.assertIn('/movie/popular', call_args.args[0])
        
        # Verify results
        self.assertEqual(len(result['results']), 2)
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_get_trending_movies_weekly(self, mock_get):
        """Test getting weekly trending movies"""
        mock_response = Mock()
        mock_response.json.return_value = {'results': []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        self.service.get_trending_movies(time_window='week')
        
        # Verify endpoint includes time window
        call_args = mock_get.call_args
        self.assertIn('/trending/movie/week', call_args.args[0])
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_get_trending_movies_daily(self, mock_get):
        """Test getting daily trending movies"""
        mock_response = Mock()
        mock_response.json.return_value = {'results': []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        self.service.get_trending_movies(time_window='day')
        
        call_args = mock_get.call_args
        self.assertIn('/trending/movie/day', call_args.args[0])
    
    def test_get_poster_url_with_path(self):
        """Test generating poster URL"""
        poster_path = '/abc123.jpg'
        url = self.service.get_poster_url(poster_path)
        
        self.assertEqual(url, 'https://image.tmdb.org/t/p/w500/abc123.jpg')
    
    def test_get_poster_url_different_size(self):
        """Test poster URL with different size"""
        poster_path = '/abc123.jpg'
        url = self.service.get_poster_url(poster_path, size='w780')
        
        self.assertEqual(url, 'https://image.tmdb.org/t/p/w780/abc123.jpg')
    
    def test_get_poster_url_none_path(self):
        """Test poster URL with None path"""
        url = self.service.get_poster_url(None)
        
        self.assertIsNone(url)
    
    def test_get_poster_url_empty_path(self):
        """Test poster URL with empty path"""
        url = self.service.get_poster_url('')
        
        self.assertIsNone(url)
    
    def test_get_backdrop_url_with_path(self):
        """Test generating backdrop URL"""
        backdrop_path = '/backdrop123.jpg'
        url = self.service.get_backdrop_url(backdrop_path)
        
        self.assertEqual(url, 'https://image.tmdb.org/t/p/w1280/backdrop123.jpg')
    
    def test_get_backdrop_url_none_path(self):
        """Test backdrop URL with None path"""
        url = self.service.get_backdrop_url(None)
        
        self.assertIsNone(url)
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_get_watch_providers_success(self, mock_get):
        """Test getting watch providers for a region"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': {
                'GB': {
                    'flatrate': [{'provider_name': 'Netflix'}],
                    'buy': [{'provider_name': 'Amazon'}]
                }
            }
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = self.service.get_watch_providers(27205, region='GB')
        
        # Verify endpoint
        call_args = mock_get.call_args
        self.assertIn('/movie/27205/watch/providers', call_args.args[0])
        
        # Verify results
        self.assertIn('flatrate', result)
        self.assertEqual(result['flatrate'][0]['provider_name'], 'Netflix')
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_get_watch_providers_no_region_data(self, mock_get):
        """Test watch providers when region has no data"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': {
                'US': {'flatrate': []}
            }
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = self.service.get_watch_providers(27205, region='GB')
        
        # Should return empty dict when region not in results
        self.assertEqual(result, {})
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_get_watch_providers_api_error(self, mock_get):
        """Test watch providers handles API errors"""
        mock_get.side_effect = requests.exceptions.RequestException('API Error')
        
        result = self.service.get_watch_providers(27205)
        
        # Should return empty dict on error
        self.assertEqual(result, {})
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_get_genres(self, mock_get):
        """Test getting genre list"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'genres': [
                {'id': 28, 'name': 'Action'},
                {'id': 35, 'name': 'Comedy'}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = self.service.get_genres()
        
        # Verify results
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'Action')
        self.assertEqual(result[1]['name'], 'Comedy')
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_get_genres_api_error(self, mock_get):
        """Test get genres handles errors"""
        mock_get.side_effect = requests.exceptions.RequestException('API Error')
        
        result = self.service.get_genres()
        
        # Should return empty list on error
        self.assertEqual(result, [])
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_search_by_genre_name_found(self, mock_get):
        """Test searching by genre name when genre exists"""
        # Mock get_genres call
        mock_response_genres = Mock()
        mock_response_genres.json.return_value = {
            'genres': [{'id': 28, 'name': 'Action'}]
        }
        mock_response_genres.raise_for_status = Mock()
        
        # Mock discover_movies call
        mock_response_discover = Mock()
        mock_response_discover.json.return_value = {
            'results': [{'id': 1, 'title': 'Action Movie'}]
        }
        mock_response_discover.raise_for_status = Mock()
        
        mock_get.side_effect = [mock_response_genres, mock_response_discover]
        
        result = self.service.search_by_genre_name('Action')
        
        # Should use discover_movies with genre_id
        self.assertEqual(len(result['results']), 1)
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_search_by_genre_name_not_found(self, mock_get):
        """Test searching by genre name when genre doesn't exist"""
        # Mock get_genres (genre not found)
        mock_response_genres = Mock()
        mock_response_genres.json.return_value = {
            'genres': [{'id': 28, 'name': 'Action'}]
        }
        mock_response_genres.raise_for_status = Mock()
        
        # Mock fallback search_movies call
        mock_response_search = Mock()
        mock_response_search.json.return_value = {'results': []}
        mock_response_search.raise_for_status = Mock()
        
        mock_get.side_effect = [mock_response_genres, mock_response_search]
        
        result = self.service.search_by_genre_name('Unknown Genre')
        
        # Should fallback to search
        self.assertEqual(result['results'], [])
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_get_similar_movies(self, mock_get):
        """Test getting similar movies"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {'id': 100, 'title': 'Similar Movie 1'},
                {'id': 101, 'title': 'Similar Movie 2'}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = self.service.get_similar_movies(27205)
        
        # Verify endpoint
        call_args = mock_get.call_args
        self.assertIn('/movie/27205/similar', call_args.args[0])
        
        # Verify results
        self.assertEqual(len(result['results']), 2)
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_get_similar_movies_api_error(self, mock_get):
        """Test similar movies handles errors"""
        mock_get.side_effect = requests.exceptions.RequestException('API Error')
        
        result = self.service.get_similar_movies(27205)
        
        # Should return empty results
        self.assertEqual(result, {'results': [], 'total_results': 0})
    
    @patch('cinemai.tmdb_service.requests.get')
    def test_timeout_handling(self, mock_get):
        """Test that all API calls have timeout parameter"""
        mock_response = Mock()
        mock_response.json.return_value = {'results': []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        self.service.search_movies('Test')
        
        # Verify timeout is set
        call_args = mock_get.call_args
        self.assertEqual(call_args.kwargs.get('timeout'), 10)


class GenreHelperTests(TestCase):
    """Test cases for genre helper functions"""
    
    def test_get_genre_id_action(self):
        """Test getting genre ID for Action"""
        genre_id = get_genre_id('action')
        self.assertEqual(genre_id, 28)
    
    def test_get_genre_id_case_insensitive(self):
        """Test genre ID lookup is case insensitive"""
        self.assertEqual(get_genre_id('ACTION'), 28)
        self.assertEqual(get_genre_id('Action'), 28)
        self.assertEqual(get_genre_id('action'), 28)
    
    def test_get_genre_id_sci_fi(self):
        """Test getting genre ID for Sci-Fi"""
        self.assertEqual(get_genre_id('sci-fi'), 878)
        self.assertEqual(get_genre_id('science fiction'), 878)
    
    def test_get_genre_id_not_found(self):
        """Test getting genre ID for unknown genre"""
        genre_id = get_genre_id('unknown')
        self.assertIsNone(genre_id)
    
    def test_genre_map_completeness(self):
        """Test that GENRE_MAP has expected genres"""
        expected_genres = [
            'action', 'comedy', 'drama', 'horror', 
            'thriller', 'romance', 'sci-fi'
        ]
        
        for genre in expected_genres:
            self.assertIn(genre, GENRE_MAP)
            self.assertIsInstance(GENRE_MAP[genre], int)