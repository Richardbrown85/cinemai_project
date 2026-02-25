/* jshint esversion: 8 */
/* global Stripe */

/**
 * CinemAI - Subscription Page JavaScript
 * Handles Stripe checkout for subscription plans
 */

/* DOM ELEMENT REFERENCES */

const stripeData = document.getElementById('stripe-data');
const subscribeBtns = document.querySelectorAll('.subscribe-btn');

/* STRIPE INITIALIZATION */

const stripe = stripeData && stripeData.dataset.stripeKey ? Stripe(stripeData.dataset.stripeKey) : null;

/* HELPER FUNCTIONS */

function getCSRFToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    
    return cookieValue;
}

function showError(message) {
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger alert-dismissible fade show';
    alert.setAttribute('role', 'alert');
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    const container = document.querySelector('.container');
    container.insertBefore(alert, container.firstChild);
    
    setTimeout(() => {
        alert.remove();
    }, 5000);
}

function showLoading(button, loading) {
    if (loading) {
        button.disabled = true;
        button.dataset.originalText = button.innerHTML;
        button.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Processing...';
    } else {
        button.disabled = false;
        button.innerHTML = button.dataset.originalText;
    }
}

/* SUBSCRIPTION HANDLING */

async function handleSubscription(tier, button) {
    if (tier === 'BASIC') {
        alert('Basic plan is completely FREE! Just sign up to get started.');
        window.location.href = '/signup/';
        return;
    }
    
    if (!stripe) {
        showError('Payment system not configured. Please contact support.');
        return;
    }
    
    showLoading(button, true);
    
    try {
        const csrfToken = getCSRFToken();
        const checkoutUrl = stripeData.dataset.checkoutUrl;
        
        const response = await fetch(checkoutUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ tier: tier })
        });
        
        const data = await response.json();
        
        if (data.sessionId) {
            const result = await stripe.redirectToCheckout({
                sessionId: data.sessionId
            });
            
            if (result.error) {
                showError(result.error.message);
            }
        } else if (data.error) {
            showError(data.error);
        } else {
            showError('Error creating checkout session');
        }
    } catch (error) {
        console.error('Subscription error:', error);
        showError('An error occurred. Please try again.');
    } finally {
        showLoading(button, false);
    }
}

/* EVENT LISTENERS */

function attachSubscriptionHandlers() {
    subscribeBtns.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const tier = e.target.dataset.tier;
            await handleSubscription(tier, e.target);
        });
    });
}

/* INITIALIZATION */

document.addEventListener('DOMContentLoaded', attachSubscriptionHandlers);