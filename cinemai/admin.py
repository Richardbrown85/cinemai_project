from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import UserProfile, Movie, Watchlist, SearchHistory

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'subscription_tier', 'subscription_active', 'created_at']
    list_filter = ['subscription_tier', 'subscription_active']
    search_fields = ['user__username', 'user__email']

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ['title', 'year', 'genre', 'rating', 'created_at']
    list_filter = ['genre', 'year']
    search_fields = ['title', 'director', 'genre']

@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'movie', 'watched', 'added_at']
    list_filter = ['watched', 'added_at']
    search_fields = ['user__username', 'movie__title']

@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'query', 'genre', 'created_at']
    list_filter = ['genre', 'created_at']
    search_fields = ['user__username', 'query']