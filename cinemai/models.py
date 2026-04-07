"""
CinemAI Models
Database models for user profiles, movies, watchlists, and search tracking.
Handles subscription tiers, rate limiting, and TMDB integration.
"""

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class SubscriptionTier(models.TextChoices):
    """Available subscription tiers with pricing"""
    BASIC = 'BASIC', 'Basic - Free'
    STANDARD = 'STANDARD', 'Standard - £9.99/month'


class SearchLog(models.Model):
    """Track user searches for rate limiting"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='search_logs')
    search_query = models.CharField(max_length=255)
    search_date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'search_date']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.search_query} ({self.search_date})"
    
    @staticmethod
    def get_daily_search_count(user, date=None):
        """Get number of searches for a user on a specific date"""
        from django.utils import timezone
        if date is None:
            date = timezone.now().date()
        return SearchLog.objects.filter(user=user, search_date=date).count()
    
    @staticmethod
    def can_search(user):
        """Check if user can perform another search based on subscription tier"""
        # Standard users have unlimited searches
        if hasattr(user, 'profile') and user.profile.subscription_tier == 'STANDARD':
            return True, 0  # unlimited
        
        # Basic users limited to 10/day
        from django.utils import timezone
        today_count = SearchLog.get_daily_search_count(user)
        limit = 10
        remaining = limit - today_count
        
        if today_count >= limit:
            return False, 0  # limit reached
        
        return True, remaining  # can search, X remaining


class UserProfile(models.Model):
    """
    Extended user profile for subscription management.
    Automatically created for each user via post_save signal.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    subscription_tier = models.CharField(
        max_length=10,
        choices=SubscriptionTier.choices,
        default=SubscriptionTier.BASIC
    )
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    subscription_active = models.BooleanField(default=False)
    subscription_end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.subscription_tier}"

    @property
    def tier_price(self):
        """Get monthly price for current subscription tier"""
        prices = {
            'BASIC': 0.00,
            'STANDARD': 9.99,
        }
        return prices.get(self.subscription_tier, 0)


# Signal handlers for automatic UserProfile creation
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile when User is created"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save UserProfile when User is saved"""
    instance.profile.save()


class Movie(models.Model):
    """
    Movie model storing TMDB data and streaming availability.
    Cached from TMDB API to reduce external API calls.
    """
    title = models.CharField(max_length=255)
    year = models.IntegerField(null=True, blank=True)
    genre = models.CharField(max_length=100, blank=True)
    director = models.CharField(max_length=255, blank=True)
    plot = models.TextField(blank=True)
    poster_url = models.URLField(max_length=500, blank=True)
    backdrop_url = models.URLField(max_length=500, blank=True, null=True)
    tmdb_id = models.IntegerField(unique=True, null=True, blank=True)
    imdb_id = models.CharField(max_length=20, null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    runtime = models.IntegerField(null=True, blank=True)  # in minutes
    release_date = models.DateField(null=True, blank=True)
    popularity = models.FloatField(null=True, blank=True)
    vote_count = models.IntegerField(null=True, blank=True)
    trailer_url = models.URLField(max_length=500, blank=True, null=True)
    
    # Streaming availability (JSON field)
    streaming_providers = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.year})" if self.year else self.title

    class Meta:
        ordering = ['-popularity', '-created_at']
        
    @property
    def genre_list(self):
        """Return genres as a list"""
        if self.genre:
            return [g.strip() for g in self.genre.split(',')]
        return []


class Watchlist(models.Model):
    """
    User's personal watchlist with watched status and notes.
    Enforces unique constraint per user-movie combination.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watchlist')
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    watched = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('user', 'movie')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.username} - {self.movie.title}"


class SearchHistory(models.Model):
    """
    Tracks all user search queries for history and analytics.
    Separate from SearchLog which is used for rate limiting.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='search_history')
    query = models.CharField(max_length=255)
    genre = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Search histories'

    def __str__(self):
        return f"{self.user.username} - {self.query}"