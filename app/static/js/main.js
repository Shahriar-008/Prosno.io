/**
 * Prosno.io - Main JavaScript
 */

document.addEventListener('DOMContentLoaded', function () {
    // ── Navbar scroll effect ──
    const navbar = document.querySelector('.navbar');
    if (navbar) {
        window.addEventListener('scroll', function () {
            if (window.scrollY > 50) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
        });
    }

    // ── Profile dropdown toggle ──
    const profileWrapper = document.getElementById('navProfileWrapper');
    const avatarBtn = document.getElementById('navAvatarBtn');
    if (avatarBtn && profileWrapper) {
        avatarBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            profileWrapper.classList.toggle('open');
        });
        document.addEventListener('click', function (e) {
            if (!profileWrapper.contains(e.target)) {
                profileWrapper.classList.remove('open');
            }
        });
    }

    // ── Mobile overlay ──
    const hamburger = document.getElementById('navHamburger');
    const mobileOverlay = document.getElementById('navMobileOverlay');
    const mobileClose = document.getElementById('navMobileClose');
    if (hamburger && mobileOverlay) {
        hamburger.addEventListener('click', function () {
            mobileOverlay.classList.add('open');
            document.body.style.overflow = 'hidden';
        });
        if (mobileClose) {
            mobileClose.addEventListener('click', function () {
                mobileOverlay.classList.remove('open');
                document.body.style.overflow = '';
            });
        }
        // Close on link click
        mobileOverlay.querySelectorAll('.nav-mobile-link, .nav-mobile-action').forEach(function (link) {
            link.addEventListener('click', function () {
                mobileOverlay.classList.remove('open');
                document.body.style.overflow = '';
            });
        });
    }

    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#') {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    const navHeight = document.querySelector('.navbar').offsetHeight;
                    const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - navHeight;
                    window.scrollTo({
                        top: targetPosition,
                        behavior: 'smooth'
                    });
                }
            }
        });
    });

    // Auto-dismiss flash messages
    const flashMessages = document.querySelectorAll('.flash-messages .alert');
    flashMessages.forEach(message => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(message);
            bsAlert.close();
        }, 5000);
    });

    // CSRF token for fetch requests
    window.getCsrfToken = function () {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    };

    // Fetch wrapper with CSRF
    window.fetchWithCsrf = function (url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            }
        };
        return fetch(url, { ...defaultOptions, ...options });
    };
});

// Helper function to format numbers
function formatNumber(num) {
    return new Intl.NumberFormat().format(num);
}

// Helper function to show toast notifications
function showToast(message, type = 'info') {
    const toastContainer = document.querySelector('.toast-container') || createToastContainer();
    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : type} border-0`;
    toastEl.setAttribute('role', 'alert');
    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    toastContainer.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl);
    toast.show();
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}

function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    document.body.appendChild(container);
    return container;
}
