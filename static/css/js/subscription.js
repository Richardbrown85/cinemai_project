/**
 * CinemAI - Subscription Page JavaScript
 * Handles Stripe checkout for subscription plans
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get Stripe public key from data attribute
    const stripePublicKey = document.getElementById('stripe-data').dataset.stripeKey;
    const stripe = Stripe(stripePublicKey);
    
    // Get all subscription buttons
    const subscribeBtns = document.querySelectorAll('.subscribe-btn');
    
    subscribeBtns.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const tier = e.target.dataset.tier;
            const originalText = btn.innerHTML;
            
            // Disable button and show loading
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Processing...';
            
            try {
                // Get CSRF token from cookie or meta tag
                const csrfToken = getCSRFToken();
                
                // Get checkout URL from data attribute
                const checkoutUrl = document.getElementById('stripe-data').dataset.checkoutUrl;
                
                // Create checkout session
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
                    // Redirect to Stripe checkout
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
                // Re-enable button
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        });
    });
});

/**
 * Get CSRF token from cookies
 */
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

/**
 * Show error message to user
 */
function showError(message) {
    // Create alert element
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger alert-dismissible fade show';
    alert.setAttribute('role', 'alert');
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Insert at top of container
    const container = document.querySelector('.container');
    container.insertBefore(alert, container.firstChild);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alert.remove();
    }, 5000);
}