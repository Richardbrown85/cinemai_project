"""
CinemAI - TMDB API Service
Handles all interactions with The Movie Database API
"""

import requests
import logging
from django.conf import settings

# Configure logger
logger = logging.getLogger(__name__)


class TMDBService:
    """Service class for TMDB API interactions"""
    
    def __init__(self):
        self.api_key = settings.TMDB_API_KEY
        self.base_url = settings.TMDB_BASE_URL
        self.image_base_url = settings.TMDB_IMAGE_BASE_URL
        
    def search_movies(self, query, page=1):
        """
        Search for movies by query
        
        Args:
            query (str): Search query
            page (int): Page number for pagination
            
        Returns:
            dict: Search results with movies
        """
        endpoint = f"{self.base_url}/search/movie"
        params = {
            'api_key': self.api_key,
            'query': query,
            'page': page,
            'language': 'en-US'
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"TMDB API Error: {e}")
            return {'results': [], 'total_results': 0}
    
    def get_movie_details(self, movie_id):
        """
        Get detailed information about a specific movie
        
        Args:
            movie_id (int): TMDB movie ID
            
        Returns:
            dict: Movie details
        """
        endpoint = f"{self.base_url}/movie/{movie_id}"
        params = {
            'api_key': self.api_key,
            'language': 'en-US',
            'append_to_response': 'videos,credits,similar'
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"TMDB API Error: {e}")
            return None
    
    def discover_movies(self, genre_id=None, sort_by='popularity.desc', page=1):
        """
        Discover movies by genre or other criteria
        
        Args:
            genre_id (int): TMDB genre ID
            sort_by (str): Sort method
            page (int): Page number
            
        Returns:
            dict: Discovered movies
        """
        endpoint = f"{self.base_url}/discover/movie"
        params = {
            'api_key': self.api_key,
            'page': page,
            'sort_by': sort_by,
            'language': 'en-US'
        }
        
        if genre_id:
            params['with_genres'] = genre_id
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"TMDB API Error: {e}")
            return {'results': [], 'total_results': 0}
    
    def get_popular_movies(self, page=1):
        """Get popular movies"""
        endpoint = f"{self.base_url}/movie/popular"
        params = {
            'api_key': self.api_key,
            'page': page,
            'language': 'en-US'
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"TMDB API Error: {e}")
            return {'results': [], 'total_results': 0}
    
    def get_trending_movies(self, time_window='week'):
        """
        Get trending movies
        
        Args:
            time_window (str): 'day' or 'week'
        """
        endpoint = f"{self.base_url}/trending/movie/{time_window}"
        params = {
            'api_key': self.api_key
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"TMDB API Error: {e}")
            return {'results': [], 'total_results': 0}
    
    def get_poster_url(self, poster_path, size='w500'):
        """
        Get full URL for movie poster
        
        Args:
            poster_path (str): Poster path from TMDB
            size (str): Image size (w92, w154, w185, w342, w500, w780, original)
            
        Returns:
            str: Full poster URL or None
        """
        if not poster_path:
            return None
        return f"{self.image_base_url}/{size}{poster_path}"
    
    def get_backdrop_url(self, backdrop_path, size='w1280'):
        """
        Get full URL for movie backdrop
        
        Args:
            backdrop_path (str): Backdrop path from TMDB
            size (str): Image size
            
        Returns:
            str: Full backdrop URL or None
        """
        if not backdrop_path:
            return None
        return f"{self.image_base_url}/{size}{backdrop_path}"
    
    def get_watch_providers(self, movie_id, region='GB'):
        """
        Get streaming availability for a movie
        
        Args:
            movie_id (int): TMDB movie ID
            region (str): Country code (GB, US, etc.)
            
        Returns:
            dict: Watch provider data
        """
        endpoint = f"{self.base_url}/movie/{movie_id}/watch/providers"
        params = {
            'api_key': self.api_key
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Get providers for specific region
            if 'results' in data and region in data['results']:
                return data['results'][region]
            return {}
        except requests.exceptions.RequestException as e:
            logger.error(f"TMDB Watch Providers Error: {e}")
            return {}
    
    def get_genres(self):
        """Get list of all movie genres"""
        endpoint = f"{self.base_url}/genre/movie/list"
        params = {
            'api_key': self.api_key,
            'language': 'en-US'
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            return response.json().get('genres', [])
        except requests.exceptions.RequestException as e:
            logger.error(f"TMDB API Error: {e}")
            return []
    
    def search_by_genre_name(self, genre_name):
        """
        Search movies by genre name
        
        Args:
            genre_name (str): Genre name (e.g., 'Action', 'Horror')
            
        Returns:
            dict: Movies in that genre
        """
        # Get all genres
        genres = self.get_genres()
        
        # Find matching genre
        genre_id = None
        for genre in genres:
            if genre['name'].lower() == genre_name.lower():
                genre_id = genre['id']
                break
        
        if genre_id:
            return self.discover_movies(genre_id=genre_id)
        else:
            # Fallback to search
            return self.search_movies(genre_name)
    
    def get_similar_movies(self, movie_id, page=1):
        """
        Get similar movies based on a movie ID
        
        Args:
            movie_id (int): TMDB movie ID
            page (int): Page number
            
        Returns:
            dict: Similar movies
        """
        endpoint = f"{self.base_url}/movie/{movie_id}/similar"
        params = {
            'api_key': self.api_key,
            'page': page,
            'language': 'en-US'
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"TMDB API Error: {e}")
            return {'results': [], 'total_results': 0}


# TMDB Genre Mapping (for reference)
GENRE_MAP = {
    'action': 28,
    'adventure': 12,
    'animation': 16,
    'comedy': 35,
    'crime': 80,
    'documentary': 99,
    'drama': 18,
    'family': 10751,
    'fantasy': 14,
    'history': 36,
    'horror': 27,
    'music': 10402,
    'mystery': 9648,
    'romance': 10749,
    'science fiction': 878,
    'sci-fi': 878,
    'tv movie': 10770,
    'thriller': 53,
    'war': 10752,
    'western': 37
}


def get_genre_id(genre_name):
    """Helper function to get genre ID from name"""
    return GENRE_MAP.get(genre_name.lower())