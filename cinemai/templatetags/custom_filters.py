from django import template
from django.utils import timezone

register = template.Library()

@register.filter
def searches_remaining(user):
    """Get remaining searches for a user today"""
    from cinemai.models import SearchLog
    
    if not user.is_authenticated:
        return 10
    
    # Standard users have unlimited
    if hasattr(user, 'profile') and user.profile.subscription_tier == 'STANDARD':
        return '∞'  # Infinity symbol
    
    # Basic users - calculate remaining
    today_count = SearchLog.get_daily_search_count(user)
    remaining = max(0, 10 - today_count)
    return remaining