"""
URL routing for the detector app.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register_user, name='register'),
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('upload/', views.upload_video, name='upload_video'),
    path('upload/delete/<int:video_id>/', views.delete_video, name='delete_video'),
    path('upload/label/<int:video_id>/', views.update_label, name='update_label'),
    path('train/', views.train_model, name='train_model'),
    path('detect/', views.detect_forgery, name='detect_forgery'),
    path('detect/run/<int:video_id>/', views.run_detection, name='run_detection'),
    path('results/<int:video_id>/', views.view_results, name='view_results'),
    path('results/', views.all_results, name='all_results'),
    path('settings/', views.settings_view, name='settings'),
    path('profile/', views.profile, name='profile'),
    
    # AJAX endpoints for interactive train workflow
    path('ajax/upload/', views.ajax_upload_video, name='ajax_upload_video'),
    path('ajax/train/', views.ajax_train_model, name='ajax_train_model'),
    path('ajax/test/', views.ajax_test_video, name='ajax_test_video'),
    
    # AJAX endpoints for interactive upload workflow
    path('ajax/upload/delete/<int:video_id>/', views.ajax_delete_video, name='ajax_delete_video'),
    path('ajax/upload/label/<int:video_id>/', views.ajax_update_label, name='ajax_update_label'),
]
