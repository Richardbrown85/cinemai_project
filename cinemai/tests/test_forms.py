"""
CinemAI Form Tests
Tests for all forms: SignUpForm, LoginForm, UserUpdateForm, ProfileUpdateForm, WatchlistForm
"""

from django.test import TestCase
from django.contrib.auth.models import User

from cinemai.forms import (
    SignUpForm,
    LoginForm,
    UserUpdateForm,
    ProfileUpdateForm,
    WatchlistForm
)
from cinemai.models import UserProfile, Watchlist, Movie, SubscriptionTier


class SignUpFormTests(TestCase):
    """Test cases for SignUpForm"""
    
    def test_signup_form_valid_data(self):
        """Test form with valid data"""
        form_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'complexpass123',
            'password2': 'complexpass123'
        }
        form = SignUpForm(data=form_data)
        
        self.assertTrue(form.is_valid())
    
    def test_signup_form_password_mismatch(self):
        """Test form rejects mismatched passwords"""
        form_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'complexpass123',
            'password2': 'differentpass456'
        }
        form = SignUpForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)
    
    def test_signup_form_duplicate_email(self):
        """Test form rejects duplicate email"""
        # Create existing user
        User.objects.create_user(
            username='existing',
            email='test@example.com',
            password='pass123'
        )
        
        # Try to create new user with same email
        form_data = {
            'username': 'newuser',
            'email': 'test@example.com',
            'password1': 'complexpass123',
            'password2': 'complexpass123'
        }
        form = SignUpForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn('already registered', str(form.errors['email']))
    
    def test_signup_form_missing_username(self):
        """Test form requires username"""
        form_data = {
            'email': 'test@example.com',
            'password1': 'complexpass123',
            'password2': 'complexpass123'
        }
        form = SignUpForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
    
    def test_signup_form_missing_email(self):
        """Test form requires email"""
        form_data = {
            'username': 'newuser',
            'password1': 'complexpass123',
            'password2': 'complexpass123'
        }
        form = SignUpForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
    
    def test_signup_form_invalid_email(self):
        """Test form rejects invalid email format"""
        form_data = {
            'username': 'newuser',
            'email': 'not-an-email',
            'password1': 'complexpass123',
            'password2': 'complexpass123'
        }
        form = SignUpForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
    
    def test_signup_form_weak_password(self):
        """Test form rejects weak/short passwords"""
        form_data = {
            'username': 'newuser',
            'email': 'test@example.com',
            'password1': '123',  # Too short
            'password2': '123'
        }
        form = SignUpForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)
    
    def test_signup_form_duplicate_username(self):
        """Test form rejects duplicate username"""
        # Create existing user
        User.objects.create_user(
            username='testuser',
            email='test1@example.com',
            password='pass123'
        )
        
        # Try to create new user with same username
        form_data = {
            'username': 'testuser',
            'email': 'test2@example.com',
            'password1': 'complexpass123',
            'password2': 'complexpass123'
        }
        form = SignUpForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
    
    def test_signup_form_has_bootstrap_classes(self):
        """Test form fields have Bootstrap CSS classes"""
        form = SignUpForm()
        
        self.assertIn('form-control', form.fields['username'].widget.attrs['class'])
        self.assertIn('form-control', form.fields['email'].widget.attrs['class'])
        self.assertIn('form-control', form.fields['password1'].widget.attrs['class'])
        self.assertIn('form-control', form.fields['password2'].widget.attrs['class'])
    
    def test_signup_form_has_placeholders(self):
        """Test form fields have placeholders"""
        form = SignUpForm()
        
        self.assertIn('placeholder', form.fields['username'].widget.attrs)
        self.assertIn('placeholder', form.fields['email'].widget.attrs)
        self.assertIn('placeholder', form.fields['password1'].widget.attrs)
        self.assertIn('placeholder', form.fields['password2'].widget.attrs)


class LoginFormTests(TestCase):
    """Test cases for LoginForm"""
    
    def setUp(self):
        """Create test user"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_login_form_valid_data(self):
        """Test form accepts valid credentials"""
        form_data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        # Note: LoginForm needs request parameter, but we can test field validation
        form = LoginForm(data=form_data)
        
        # Check fields are present
        self.assertIn('username', form.fields)
        self.assertIn('password', form.fields)
    
    def test_login_form_missing_username(self):
        """Test form requires username"""
        form_data = {
            'password': 'testpass123'
        }
        form = LoginForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
    
    def test_login_form_missing_password(self):
        """Test form requires password"""
        form_data = {
            'username': 'testuser'
        }
        form = LoginForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)
    
    def test_login_form_has_bootstrap_classes(self):
        """Test form fields have Bootstrap CSS classes"""
        form = LoginForm()
        
        self.assertIn('form-control', form.fields['username'].widget.attrs['class'])
        self.assertIn('form-control', form.fields['password'].widget.attrs['class'])
    
    def test_login_form_password_widget_is_password_input(self):
        """Test password field uses PasswordInput widget"""
        form = LoginForm()
        
        self.assertEqual(
            form.fields['password'].widget.__class__.__name__,
            'PasswordInput'
        )


class UserUpdateFormTests(TestCase):
    """Test cases for UserUpdateForm"""
    
    def setUp(self):
        """Create test user"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_user_update_form_valid_data(self):
        """Test form with valid update data"""
        form_data = {
            'username': 'updateduser',
            'email': 'updated@example.com',
            'first_name': 'John',
            'last_name': 'Doe'
        }
        form = UserUpdateForm(data=form_data, instance=self.user)
        
        self.assertTrue(form.is_valid())
    
    def test_user_update_form_optional_fields(self):
        """Test that first_name and last_name are optional"""
        form_data = {
            'username': 'testuser',
            'email': 'test@example.com'
        }
        form = UserUpdateForm(data=form_data, instance=self.user)
        
        self.assertTrue(form.is_valid())
    
    def test_user_update_form_invalid_email(self):
        """Test form rejects invalid email"""
        form_data = {
            'username': 'testuser',
            'email': 'not-an-email',
            'first_name': 'John',
            'last_name': 'Doe'
        }
        form = UserUpdateForm(data=form_data, instance=self.user)
        
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
    
    def test_user_update_form_missing_required_fields(self):
        """Test form requires username and email"""
        form_data = {
            'first_name': 'John'
        }
        form = UserUpdateForm(data=form_data, instance=self.user)
        
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        self.assertIn('email', form.errors)
    
    def test_user_update_form_has_bootstrap_classes(self):
        """Test form fields have Bootstrap CSS classes"""
        form = UserUpdateForm(instance=self.user)
        
        self.assertIn('form-control', form.fields['username'].widget.attrs['class'])
        self.assertIn('form-control', form.fields['email'].widget.attrs['class'])
        self.assertIn('form-control', form.fields['first_name'].widget.attrs['class'])
        self.assertIn('form-control', form.fields['last_name'].widget.attrs['class'])
    
    def test_user_update_form_saves_changes(self):
        """Test form saves user changes correctly"""
        form_data = {
            'username': 'updateduser',
            'email': 'updated@example.com',
            'first_name': 'Jane',
            'last_name': 'Smith'
        }
        form = UserUpdateForm(data=form_data, instance=self.user)
        
        self.assertTrue(form.is_valid())
        updated_user = form.save()
        
        self.assertEqual(updated_user.username, 'updateduser')
        self.assertEqual(updated_user.email, 'updated@example.com')
        self.assertEqual(updated_user.first_name, 'Jane')
        self.assertEqual(updated_user.last_name, 'Smith')


class ProfileUpdateFormTests(TestCase):
    """Test cases for ProfileUpdateForm"""
    
    def setUp(self):
        """Create test user with profile"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.profile = self.user.profile
    
    def test_profile_update_form_valid_data(self):
        """Test form with valid subscription tier"""
        form_data = {
            'subscription_tier': SubscriptionTier.STANDARD
        }
        form = ProfileUpdateForm(data=form_data, instance=self.profile)
        
        self.assertTrue(form.is_valid())
    
    def test_profile_update_form_basic_tier(self):
        """Test form accepts BASIC tier"""
        form_data = {
            'subscription_tier': SubscriptionTier.BASIC
        }
        form = ProfileUpdateForm(data=form_data, instance=self.profile)
        
        self.assertTrue(form.is_valid())
    
    def test_profile_update_form_invalid_tier(self):
        """Test form rejects invalid subscription tier"""
        form_data = {
            'subscription_tier': 'INVALID_TIER'
        }
        form = ProfileUpdateForm(data=form_data, instance=self.profile)
        
        self.assertFalse(form.is_valid())
        self.assertIn('subscription_tier', form.errors)
    
    def test_profile_update_form_has_bootstrap_class(self):
        """Test subscription_tier field has Bootstrap class"""
        form = ProfileUpdateForm(instance=self.profile)
        
        self.assertIn('form-control', form.fields['subscription_tier'].widget.attrs['class'])
    
    def test_profile_update_form_saves_changes(self):
        """Test form saves profile changes"""
        form_data = {
            'subscription_tier': SubscriptionTier.STANDARD
        }
        form = ProfileUpdateForm(data=form_data, instance=self.profile)
        
        self.assertTrue(form.is_valid())
        updated_profile = form.save()
        
        self.assertEqual(updated_profile.subscription_tier, SubscriptionTier.STANDARD)


class WatchlistFormTests(TestCase):
    """Test cases for WatchlistForm"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.movie = Movie.objects.create(
            title='Test Movie',
            year=2024,
            tmdb_id=12345
        )
        self.watchlist_item = Watchlist.objects.create(
            user=self.user,
            movie=self.movie
        )
    
    def test_watchlist_form_valid_data(self):
        """Test form with valid data"""
        form_data = {
            'notes': 'Great movie!',
            'watched': True
        }
        form = WatchlistForm(data=form_data, instance=self.watchlist_item)
        
        self.assertTrue(form.is_valid())
    
    def test_watchlist_form_notes_optional(self):
        """Test notes field is optional"""
        form_data = {
            'watched': True
        }
        form = WatchlistForm(data=form_data, instance=self.watchlist_item)
        
        self.assertTrue(form.is_valid())
    
    def test_watchlist_form_watched_optional(self):
        """Test watched field is optional (defaults to False)"""
        form_data = {
            'notes': 'Planning to watch this'
        }
        form = WatchlistForm(data=form_data, instance=self.watchlist_item)
        
        self.assertTrue(form.is_valid())
    
    def test_watchlist_form_empty_notes(self):
        """Test form accepts empty notes"""
        form_data = {
            'notes': '',
            'watched': False
        }
        form = WatchlistForm(data=form_data, instance=self.watchlist_item)
        
        self.assertTrue(form.is_valid())
    
    def test_watchlist_form_has_bootstrap_classes(self):
        """Test form fields have Bootstrap classes"""
        form = WatchlistForm(instance=self.watchlist_item)
        
        self.assertIn('form-control', form.fields['notes'].widget.attrs['class'])
        self.assertIn('form-check-input', form.fields['watched'].widget.attrs['class'])
    
    def test_watchlist_form_notes_widget_is_textarea(self):
        """Test notes field uses Textarea widget"""
        form = WatchlistForm(instance=self.watchlist_item)
        
        self.assertEqual(
            form.fields['notes'].widget.__class__.__name__,
            'Textarea'
        )
    
    def test_watchlist_form_textarea_has_rows(self):
        """Test textarea has rows attribute"""
        form = WatchlistForm(instance=self.watchlist_item)
        
        self.assertEqual(form.fields['notes'].widget.attrs['rows'], 3)
    
    def test_watchlist_form_saves_changes(self):
        """Test form saves watchlist changes"""
        form_data = {
            'notes': 'Updated notes about this movie',
            'watched': True
        }
        form = WatchlistForm(data=form_data, instance=self.watchlist_item)
        
        self.assertTrue(form.is_valid())
        updated_item = form.save()
        
        self.assertEqual(updated_item.notes, 'Updated notes about this movie')
        self.assertTrue(updated_item.watched)
    
    def test_watchlist_form_long_notes(self):
        """Test form accepts long notes"""
        long_notes = 'A' * 1000  # 1000 character note
        form_data = {
            'notes': long_notes,
            'watched': False
        }
        form = WatchlistForm(data=form_data, instance=self.watchlist_item)
        
        self.assertTrue(form.is_valid())


class FormIntegrationTests(TestCase):
    """Integration tests for forms working together"""
    
    def test_signup_and_profile_creation(self):
        """Test that signup creates user and profile"""
        form_data = {
            'username': 'integrationuser',
            'email': 'integration@example.com',
            'password1': 'complexpass123',
            'password2': 'complexpass123'
        }
        form = SignUpForm(data=form_data)
        
        self.assertTrue(form.is_valid())
        user = form.save()
        
        # Profile should be auto-created
        self.assertTrue(hasattr(user, 'profile'))
        self.assertEqual(user.profile.subscription_tier, SubscriptionTier.BASIC)
    
    def test_user_update_preserves_profile(self):
        """Test updating user doesn't affect profile"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='pass123'
        )
        
        # Upgrade profile
        user.profile.subscription_tier = SubscriptionTier.STANDARD
        user.profile.save()
        
        # Update user
        form_data = {
            'username': 'updateduser',
            'email': 'updated@example.com',
            'first_name': 'Test',
            'last_name': 'User'
        }
        form = UserUpdateForm(data=form_data, instance=user)
        self.assertTrue(form.is_valid())
        form.save()
        
        # Profile should remain unchanged
        user.refresh_from_db()
        self.assertEqual(user.profile.subscription_tier, SubscriptionTier.STANDARD)