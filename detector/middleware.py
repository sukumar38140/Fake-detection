from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

class SecureSessionMiddleware(MiddlewareMixin):
    """
    Middleware to ensure session security and prevent data leakage.
    Adds headers to prevent browser caching of sensitive user data.
    """
    def process_response(self, request, response):
        # Prevent caching for authenticated users to avoid data leakage on shared devices
        if request.user.is_authenticated:
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        
        return response
