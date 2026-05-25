/**
 * Main JavaScript for Fake Video Detection System
 * Handles video uploads, deletions, label updates, and form interactions
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all handlers
    initializeDeleteButtons();
    initializeLabelSelects();
    initializeFileUpload();
    initializeFormValidation();
});

/**
 * Initialize delete button functionality
 */
function initializeDeleteButtons() {
    const deleteButtons = document.querySelectorAll('.delete-btn');
    
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const videoId = this.getAttribute('data-id');
            
            // Confirm before deleting
            if (confirm('Are you sure you want to delete this video? This action cannot be undone.')) {
                deleteVideo(videoId);
            }
        });
    });
}

/**
 * Delete video via AJAX
 */
function deleteVideo(videoId) {
    // Use the AJAX endpoint for async deletion
    const formData = new FormData();
    
    fetch(`/ajax/upload/delete/${videoId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Remove the video row from the table
            const videoRow = document.getElementById(`video-row-${videoId}`);
            if (videoRow) {
                videoRow.style.opacity = '0';
                setTimeout(() => {
                    videoRow.remove();
                    showNotification('Video deleted successfully', 'success');
                    // Refresh the page after 1 second to update stats
                    setTimeout(() => location.reload(), 1000);
                }, 300);
            }
        } else {
            showNotification(data.message || 'Failed to delete video', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error deleting video', 'error');
    });
}

/**
 * Initialize label select dropdowns
 */
function initializeLabelSelects() {
    const labelSelects = document.querySelectorAll('.label-select');
    
    labelSelects.forEach(select => {
        select.addEventListener('change', function() {
            const videoId = this.getAttribute('data-id');
            const newLabel = this.value;
            updateLabel(videoId, newLabel);
        });
    });
}

/**
 * Update video label via AJAX
 */
function updateLabel(videoId, newLabel) {
    const formData = new FormData();
    formData.append('label', newLabel);
    
    fetch(`/ajax/upload/label/${videoId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
        },
        body: formData,
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            showNotification(`Label updated to ${newLabel}`, 'success');
        } else {
            showNotification(data.message || 'Failed to update label', 'error');
            // Revert the select
            location.reload();
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error updating label', 'error');
        location.reload();
    });
}

/**
 * Initialize file upload with drag and drop
 */
function initializeFileUpload() {
    const fileInput = document.getElementById('video-file');
    const dropZone = document.getElementById('file-drop-zone');
    
    if (!fileInput || !dropZone) return;
    
    // Click to browse
    dropZone.addEventListener('click', function(e) {
        if (e.target !== fileInput) {
            fileInput.click();
        }
    });
    
    // File input change
    fileInput.addEventListener('change', function() {
        updateFileInfo(this.files[0]);
    });
    
    // Drag and drop events
    dropZone.addEventListener('dragover', function(e) {
        e.preventDefault();
        e.stopPropagation();
        this.classList.add('dragover');
    });
    
    dropZone.addEventListener('dragleave', function(e) {
        e.preventDefault();
        e.stopPropagation();
        this.classList.remove('dragover');
    });
    
    dropZone.addEventListener('drop', function(e) {
        e.preventDefault();
        e.stopPropagation();
        this.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            updateFileInfo(files[0]);
        }
    });
    
    // Prevent default drag behavior on document
    document.addEventListener('dragover', function(e) {
        e.preventDefault();
    });
    
    document.addEventListener('drop', function(e) {
        e.preventDefault();
    });
}

/**
 * Update file info display
 */
function updateFileInfo(file) {
    if (!file) return;
    
    const fileInfo = document.getElementById('file-info');
    const fileName = document.getElementById('file-name');
    const fileSize = document.getElementById('file-size');
    
    if (fileName) {
        fileName.textContent = file.name;
    }
    if (fileSize) {
        const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
        fileSize.textContent = `${sizeMB} MB`;
    }
    
    if (fileInfo) {
        fileInfo.style.display = 'flex';
    }
    
    // Validate file size on client side
    const maxSize = 1073741824; // 1GB
    if (file.size > maxSize) {
        showNotification(`File size exceeds 1GB limit (${(file.size / (1024 * 1024 * 1024)).toFixed(2)}GB)`, 'error');
        document.getElementById('video-file').value = '';
        if (fileInfo) fileInfo.style.display = 'none';
        return false;
    }
    
    // Validate file type
    const validExtensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.mpeg', '.mpg', '.3gp', '.m4v'];
    const fileExt = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!validExtensions.includes(fileExt)) {
        showNotification(`Unsupported format. Supported: ${validExtensions.join(', ')}`, 'error');
        document.getElementById('video-file').value = '';
        if (fileInfo) fileInfo.style.display = 'none';
        return false;
    }
}

/**
 * Initialize form validation
 */
function initializeFormValidation() {
    const uploadForm = document.getElementById('upload-form');
    
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            const fileInput = document.getElementById('video-file');
            const titleInput = document.getElementById('video-title');
            
            // Check if file is selected
            if (!fileInput.files || fileInput.files.length === 0) {
                e.preventDefault();
                showNotification('Please select a video file', 'error');
                return false;
            }
            
            // Optional: Show progress
            const submitBtn = uploadForm.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Uploading...';
            }
        });
    }
}

/**
 * Get CSRF token from cookies
 */
function getCookie(name) {
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
 * Show notification message
 */
function showNotification(message, type = 'info') {
    // Create notification element if it doesn't exist
    let notificationContainer = document.getElementById('notification-container');
    
    if (!notificationContainer) {
        notificationContainer = document.createElement('div');
        notificationContainer.id = 'notification-container';
        notificationContainer.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 400px;
        `;
        document.body.appendChild(notificationContainer);
    }
    
    // Create notification element
    const notification = document.createElement('div');
    notification.style.cssText = `
        padding: 12px 16px;
        margin-bottom: 10px;
        border-radius: 6px;
        font-size: 14px;
        animation: slideIn 0.3s ease-out;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    `;
    
    // Set colors based on type
    const colors = {
        'success': { bg: '#d4edda', text: '#155724', border: '#c3e6cb' },
        'error': { bg: '#f8d7da', text: '#721c24', border: '#f5c6cb' },
        'warning': { bg: '#fff3cd', text: '#856404', border: '#ffeeba' },
        'info': { bg: '#d1ecf1', text: '#0c5460', border: '#bee5eb' }
    };
    
    const color = colors[type] || colors['info'];
    notification.style.backgroundColor = color.bg;
    notification.style.color = color.text;
    notification.style.border = `1px solid ${color.border}`;
    notification.textContent = message;
    
    notificationContainer.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

/**
 * Add CSS animations
 */
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
    
    .dragover {
        background-color: rgba(99, 102, 241, 0.1) !important;
        border-color: #6366f1 !important;
    }
`;
document.head.appendChild(style);

// Export functions for global use
window.deleteVideo = deleteVideo;
window.updateLabel = updateLabel;
