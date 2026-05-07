/**
 * ForgeGuard AI - Main JavaScript
 * Handles sidebar toggle, auto-dismiss alerts, and interactive features.
 */

// ── Sidebar Toggle ──
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
        sidebar.classList.toggle('open');
    }
}

// Close sidebar on outside click (mobile)
document.addEventListener('click', function(e) {
    const sidebar = document.getElementById('sidebar');
    const menuToggle = document.getElementById('menu-toggle');
    if (sidebar && sidebar.classList.contains('open')) {
        if (!sidebar.contains(e.target) && !menuToggle.contains(e.target)) {
            sidebar.classList.remove('open');
        }
    }
});

// ── Auto-dismiss alerts after 5 seconds ──
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert, index) {
        setTimeout(function() {
            alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(function() {
                alert.remove();
            }, 400);
        }, 5000 + (index * 500));
    });
});

// ── Animate stat values on scroll ──
function animateStats() {
    const statValues = document.querySelectorAll('.stat-value');
    statValues.forEach(function(el) {
        const text = el.textContent.trim();
        const value = parseInt(text);
        // Skip if NaN, already animated, or text is not a pure integer
        if (isNaN(value) || el.dataset.animated || text !== String(value)) return;

        el.dataset.animated = 'true';
        let current = 0;
        const increment = Math.max(1, Math.ceil(value / 30));
        const timer = setInterval(function() {
            current += increment;
            if (current >= value) {
                current = value;
                clearInterval(timer);
            }
            el.textContent = current;
        }, 30);
    });
}

// Run animation on page load
document.addEventListener('DOMContentLoaded', animateStats);

// ── Card entrance animations ──
document.addEventListener('DOMContentLoaded', function() {
    const cards = document.querySelectorAll('.card, .stat-card, .video-card');
    cards.forEach(function(card, index) {
        card.style.opacity = '0';
        card.style.transform = 'translateY(15px)';
        setTimeout(function() {
            card.style.transition = 'opacity 0.45s ease, transform 0.45s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 60 + (index * 60));
    });
});

// ── Training form submit spinner ──
document.addEventListener('DOMContentLoaded', function() {
    const trainForm = document.getElementById('train-form');
    if (trainForm) {
        trainForm.addEventListener('submit', function() {
            const btn = document.getElementById('start-training-btn');
            if (btn && !btn.disabled) {
                btn.innerHTML = '<span class="spinner"></span> Training in progress...';
                btn.style.pointerEvents = 'none';
                btn.style.opacity = '0.7';
            }
        });
    }
});

// ── Upload form progress simulation ──
document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('upload-form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', function() {
            const progressContainer = document.getElementById('upload-progress');
            const progressFill = document.getElementById('progress-fill');
            const progressText = document.getElementById('progress-text');

            if (progressContainer) {
                progressContainer.style.display = 'block';
                let progress = 0;
                const timer = setInterval(function() {
                    progress += Math.random() * 15;
                    if (progress >= 90) {
                        progress = 90;
                        clearInterval(timer);
                        progressText.textContent = 'Processing...';
                    }
                    progressFill.style.width = progress + '%';
                    progressText.textContent = 'Uploading... ' + Math.round(progress) + '%';
                }, 200);
            }

            const btn = document.getElementById('upload-submit');
            if (btn) {
                btn.innerHTML = '<span class="spinner"></span> Uploading...';
                btn.style.pointerEvents = 'none';
                btn.style.opacity = '0.7';
            }
        });
    }
});
// ── Session & Cache Cleanup ──
function handleLogout(event) {
    // Clear all client-side state
    localStorage.clear();
    sessionStorage.clear();
    
    // Clear cookies if possible (optional, as server handles logout)
    document.cookie.split(";").forEach(function(c) { 
        document.cookie = c.replace(/^ +/, "").replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/"); 
    });
    
    console.log('Session data cleared locally.');
}

// Attach logout handler to logout links
document.addEventListener('DOMContentLoaded', function() {
    const logoutLinks = document.querySelectorAll('a[href*="logout"]');
    logoutLinks.forEach(link => {
        link.addEventListener('click', handleLogout);
    });
});
