"""
CinemAI Forms
Django forms for user authentication, profile management, and watchlist functionality.
All forms include Bootstrap styling for consistent UI.
"""

from django import forms

# Create your forms here.
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import UserProfile, Watchlist


class SignUpForm(UserCreationForm):
    """
    User registration form with email validation.
    Extends Django's UserCreationForm with email field and Bootstrap styling.
    """
    email = forms.EmailField(
        max_length=254,
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email address'
        })
    )
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username'
        })
    )
    password1 = forms.CharField(
        label='Create Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create Password'
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm Password'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_email(self):
        """Validate email uniqueness"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email


class LoginForm(AuthenticationForm):
    """
    User login form with Bootstrap styling.
    Extends Django's AuthenticationForm.
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )


class UserUpdateForm(forms.ModelForm):
    """
    User account update form.
    Allows users to update username, email, and optional name fields.
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control'
        })
    )
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']


class ProfileUpdateForm(forms.ModelForm):
    """
    Subscription tier update form.
    Allows users to change their subscription level.
    """
    class Meta:
        model = UserProfile
        fields = ['subscription_tier']
        widgets = {
            'subscription_tier': forms.Select(attrs={
                'class': 'form-control'
            })
        }


class WatchlistForm(forms.ModelForm):
    """
    Watchlist item update form.
    Allows users to mark movies as watched and add personal notes.
    """
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add notes about this movie...'
        })
    )

    class Meta:
        model = Watchlist
        fields = ['notes', 'watched']
        widgets = {
            'watched': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }