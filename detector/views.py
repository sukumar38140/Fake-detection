"""
Views for the Video Forgery Detection System.
Handles dashboard, upload, training, detection, and results visualization.
"""
import os
import time
import json
import traceback
import shutil
import re
import cv2

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import Video, AnalysisResult, ForgeryRegion, TrainingSession, UserProfile
from .forms import (
    UserRegistrationForm,
    VideoUploadForm,
    TrainingConfigForm,
    ProfileForm,
    UserSettingsForm,
)
from .ml.frame_extractor import get_video_info, extract_frames
from .ml.trainer import train_model as run_training
from .ml.predictor import predict_video
from .ml.region_detector import detect_forgery_regions, annotate_frame


def register_user(request):
    """Handle user registration."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome to the Forensic Tool, {user.username}!')
            return redirect('dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = UserRegistrationForm()
    return render(request, 'detector/register.html', {'form': form})


def login_user(request):
    """Handle user login."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm()
    return render(request, 'detector/login.html', {'form': form})


def logout_user(request):
    """Handle user logout."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


@login_required
def dashboard(request):
    """Main dashboard with system overview and statistics."""
    # Stats for sample videos (used for training)
    sample_videos = Video.objects.filter(video_type='sample', user=request.user)
    total_samples = sample_videos.count()
    real_samples = sample_videos.filter(label='real').count()
    fake_samples = sample_videos.filter(label='fake').count()
    
    # Stats for test videos (used for detection)
    test_videos = Video.objects.filter(video_type='test', user=request.user)
    total_tests = test_videos.count()
    
    # Analysis results from test videos only
    analyzed_tests = AnalysisResult.objects.filter(video__video_type='test', video__user=request.user).count()
    fake_detected = AnalysisResult.objects.filter(video__video_type='test', verdict='fake', video__user=request.user).count()
    real_detected = AnalysisResult.objects.filter(video__video_type='test', verdict='real', video__user=request.user).count()
    
    training_sessions = TrainingSession.objects.filter(user=request.user).count()
    latest_session = TrainingSession.objects.filter(user=request.user, status='completed').first()

    # Check if user has a trained model
    model_exists = latest_session is not None and os.path.exists(latest_session.model_path) if latest_session else False

    # Get current test video (last uploaded)
    current_test_video = test_videos.order_by('-uploaded_at').first()
    current_result = None
    if current_test_video:
        current_result = AnalysisResult.objects.filter(video=current_test_video).first()

    # Recent analysis results from test videos
    recent_results = AnalysisResult.objects.filter(video__video_type='test', video__user=request.user).select_related('video').all()[:5]

    context = {
        'total_samples': total_samples,
        'real_samples': real_samples,
        'fake_samples': fake_samples,
        'total_tests': total_tests,
        'analyzed_tests': analyzed_tests,
        'fake_detected': fake_detected,
        'real_detected': real_detected,
        'training_sessions': training_sessions,
        'latest_session': latest_session,
        'model_exists': model_exists,
        'current_test_video': current_test_video,
        'current_result': current_result,
        'recent_results': recent_results,
    }
    return render(request, 'detector/dashboard.html', context)


@login_required
def upload_video(request):
    """
    Handle video file upload - separated for samples and test videos.
    
    Supported formats: MP4, AVI, MOV, MKV, WMV, FLV, WEBM, MPEG, MPG, 3GP, M4V
    Maximum file size: 1GB
    """
    if request.method == 'POST':
        form = VideoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            video = form.save(commit=False)
            video.user = request.user
            
            # Use filename if title is empty
            if not video.title:
                video.title = request.FILES['video_file'].name.split('.')[0]

            # Calculate file size in MB
            video_file = request.FILES['video_file']
            video.file_size_mb = video_file.size / (1024 * 1024)
            
            # Backend validation: Check file size (1GB max)
            max_size_bytes = 1073741824  # 1GB
            if video_file.size > max_size_bytes:
                messages.error(
                    request,
                    f'File size {video.file_size_mb:.2f}MB exceeds 1GB limit. Please upload a smaller video.'
                )
                return redirect('upload_video')
            
            # Backend validation: Check file format (as per documentation)
            valid_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.mpeg', '.mpg', '.3gp', '.m4v']
            ext = '.' + video_file.name.split('.')[-1].lower()
            if ext not in valid_extensions:
                messages.error(
                    request,
                    f'Unsupported video format "{ext.upper()}". Supported: MP4, AVI, MOV, MKV, WMV, FLV, WEBM, MPEG, MPG, 3GP, M4V'
                )
                return redirect('upload_video')
            
            # Initialize status and label as per documentation
            video.status = 'uploaded'  # Initial status: Uploaded
            video.label = 'unlabeled'   # Initial label: Unlabeled
            video.save()

            # Extract video metadata using OpenCV
            try:
                info = get_video_info(video.video_path)
                video.frame_count = info['total_frames']
                video.duration_seconds = info['duration']
                video.save()
            except Exception as e:
                # Log error but don't prevent upload
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Metadata extraction failed for video {video.id}: {str(e)}")
                messages.warning(request, 'Video uploaded but metadata extraction failed. You can still use it.')

            video_type_display = 'Sample' if video.video_type == 'sample' else 'Test'
            messages.success(
                request,
                f'✓ {video_type_display} video "{video.title}" uploaded successfully! '
                f'({video.file_size_mb:.1f}MB • Status: Uploaded • Label: Unlabeled)'
            )
            return redirect('upload_video')
        else:
            # Display form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        video_type = request.GET.get('type', 'sample')
        form = VideoUploadForm(initial={'video_type': video_type})

    # Separate sample and test videos (for management display)
    sample_videos = Video.objects.filter(video_type='sample', user=request.user).order_by('-uploaded_at')
    test_videos = Video.objects.filter(video_type='test', user=request.user).order_by('-uploaded_at')
    labeled_sample_count = sample_videos.exclude(label='unlabeled').count()

    context = {
        'form': form,
        'sample_videos': sample_videos,
        'test_videos': test_videos,
        'labeled_sample_count': labeled_sample_count,
        'max_file_size_gb': 1,  # Pass to template for client-side display
        'supported_formats': 'MP4, AVI, MOV, MKV, WMV, FLV, WEBM, MPEG, MPG, 3GP, M4V',
    }
    return render(request, 'detector/upload.html', context)


@login_required
def profile(request):
    """Allow users to view and update their profile and password."""
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        if 'profile_submit' in request.POST:
            form = ProfileForm(request.POST, request.FILES, instance=request.user, profile_instance=profile_obj)
            password_form = PasswordChangeForm(request.user)
            if form.is_valid():
                user = form.save()
                # Update UserProfile fields
                profile_obj.display_name = form.cleaned_data.get('display_name', profile_obj.display_name)
                profile_obj.phone = form.cleaned_data.get('phone', profile_obj.phone)
                if 'avatar' in request.FILES:
                    profile_obj.avatar = request.FILES['avatar']
                profile_obj.save()
                messages.success(request, 'Profile updated successfully.')
                return redirect('profile')
        elif 'password_submit' in request.POST:
            form = ProfileForm(instance=request.user, profile_instance=profile_obj)
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Password changed successfully.')
                return redirect('profile')
    else:
        form = ProfileForm(instance=request.user, profile_instance=profile_obj)
        password_form = PasswordChangeForm(request.user)

    context = {
        'form': form,
        'password_form': password_form,
        'profile': profile_obj,
    }
    return render(request, 'detector/profile.html', context)


@login_required
def settings_view(request):
    """User-specific workflow settings and model preferences."""
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        if 'delete_model' in request.POST:
            latest_session = TrainingSession.objects.filter(user=request.user, status='completed').first()
            if latest_session and latest_session.model_path and os.path.exists(latest_session.model_path):
                try:
                    os.remove(latest_session.model_path)
                    latest_session.model_path = ""
                    latest_session.status = "failed"
                    latest_session.error_message = "Model deleted by user"
                    latest_session.save()
                    messages.success(request, 'Model file deleted successfully.')
                except Exception as e:
                    messages.error(request, f'Failed to delete model: {str(e)}')
            return redirect('settings')
            
        form = UserSettingsForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings saved successfully.')
            return redirect('settings')
    else:
        form = UserSettingsForm(instance=profile_obj)

    # Calculate cache size (frames directory)
    cache_size = 0
    frames_root = os.path.join(settings.MEDIA_ROOT, 'frames')
    if os.path.exists(frames_root):
        for root, dirs, files in os.walk(frames_root):
            for f in files:
                cache_size += os.path.getsize(os.path.join(root, f))
    
    latest_session = TrainingSession.objects.filter(user=request.user, status='completed').first()
    model_exists = latest_session is not None and os.path.exists(latest_session.model_path) if latest_session else False

    context = {
        'form': form,
        'profile': profile_obj,
        'model_exists': model_exists,
        'cache_size': round(cache_size / (1024 * 1024), 1),
    }
    return render(request, 'detector/settings.html', context)


@require_POST
@login_required
def delete_video(request, video_id):
    """Delete an uploaded video."""
    video = get_object_or_404(Video, id=video_id, user=request.user)
    title = video.title

    # Delete video file and frames
    if video.video_file and os.path.exists(video.video_path):
        os.remove(video.video_path)
    if os.path.exists(video.frames_dir):
        shutil.rmtree(video.frames_dir)

    video.delete()
    messages.success(request, f'Video "{title}" deleted.')
    return redirect('upload_video')


@require_POST
@login_required
def update_label(request, video_id):
    """Update a video's label (real/fake)."""
    video = get_object_or_404(Video, id=video_id, user=request.user)
    new_label = request.POST.get('label', 'unlabeled')
    if new_label in ['real', 'fake', 'unlabeled']:
        video.label = new_label
        video.save()
        messages.success(request, f'Label for "{video.title}" updated to {new_label}.')
    return redirect('upload_video')


@login_required
def train_model(request):
    """Model training page and handler."""
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = TrainingConfigForm(request.POST)
        if form.is_valid():
            epochs = form.cleaned_data['epochs']
            batch_size = form.cleaned_data['batch_size']
            validation_split = form.cleaned_data['validation_split']

            # Check for labeled sample videos
            real_count = Video.objects.filter(label='real', video_type='sample', user=request.user).count()
            fake_count = Video.objects.filter(label='fake', video_type='sample', user=request.user).count()

            if real_count == 0 or fake_count == 0:
                messages.error(
                    request,
                    f'Need at least 1 real AND 1 fake sample video. '
                    f'Currently: {real_count} real, {fake_count} fake. '
                    f'Go to Upload page to upload and label your sample videos.'
                )
                return redirect('train_model')

            # Create training session
            session = TrainingSession.objects.create(
                user=request.user,
                epochs=epochs,
                batch_size=batch_size,
            )

            # Run training
            try:
                labeled_videos = Video.objects.filter(video_type='sample', user=request.user).exclude(label='unlabeled')

                result = run_training(
                    training_session=session,
                    videos_queryset=labeled_videos,
                    epochs=epochs,
                    batch_size=batch_size,
                    validation_split=validation_split,
                )

                messages.success(
                    request,
                    f'Training completed! Accuracy: {result["final_accuracy"]:.1%}, '
                    f'Val Accuracy: {result.get("val_accuracy", 0):.1%}'
                )
            except Exception as e:
                messages.error(request, f'Training failed: {str(e)}')

            return redirect('train_model')
    else:
        form = TrainingConfigForm()

    # Get training history
    sessions = TrainingSession.objects.filter(user=request.user)[:10]
    latest_session = TrainingSession.objects.filter(user=request.user, status='completed').first()
    model_exists = latest_session is not None and os.path.exists(latest_session.model_path) if latest_session else False

    # Dataset stats for sample videos
    real_count = Video.objects.filter(label='real', video_type='sample', user=request.user).count()
    fake_count = Video.objects.filter(label='fake', video_type='sample', user=request.user).count()
    total_labeled = real_count + fake_count

    context = {
        'form': form,
        'sessions': sessions,
        'model_exists': model_exists,
        'real_count': real_count,
        'fake_count': fake_count,
        'total_labeled': total_labeled,
        'profile': profile_obj,
    }
    return render(request, 'detector/train.html', context)


@login_required
def detect_forgery(request):
    """Video forgery detection page - show only test video if exists."""
    # Get the current test video (last uploaded test video)
    test_video = Video.objects.filter(video_type='test', user=request.user).order_by('-uploaded_at').first()
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    
    latest_session = TrainingSession.objects.filter(user=request.user, status='completed').first()
    model_exists = latest_session is not None and os.path.exists(latest_session.model_path) if latest_session else False

    context = {
        'video': test_video,
        'model_exists': model_exists,
        'profile': profile_obj,
    }
    return render(request, 'detector/detect.html', context)


@login_required
def run_detection(request, video_id):
    """Run forgery detection on a specific video."""
    video = get_object_or_404(Video, id=video_id, user=request.user)

    latest_session = TrainingSession.objects.filter(user=request.user, status='completed').first()
    if not latest_session or not latest_session.model_path or not os.path.exists(latest_session.model_path):
        messages.error(request, 'No trained model found. Please train a model first.')
        return redirect('detect_forgery')

    model_path = latest_session.model_path

    try:
        video.status = 'processing'
        video.save()

        # Run prediction
        profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
        result = predict_video(
            video.video_path,
            model_path,
            max_frames=profile_obj.preferred_frame_sample_rate * 2 # Analyze more frames if user wants higher sample rate
        )

        # Save results to database
        analysis, created = AnalysisResult.objects.update_or_create(
            video=video,
            defaults={
                'verdict': result['verdict'],
                'confidence': result['confidence'],
                'total_frames_analyzed': result['total_frames_analyzed'],
                'fake_frame_count': result['fake_frame_count'],
                'real_frame_count': result['real_frame_count'],
                'frame_predictions': result['frame_predictions'],
                'processing_time_seconds': result['processing_time'],
            }
        )

        # If fake, detect forgery regions
        if result['verdict'] == 'fake':
            profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
            _process_forgery_regions(
                analysis,
                result,
                video,
                threshold=profile_obj.detection_threshold,
                show_heatmap=profile_obj.show_heatmap,
            )

        video.status = 'analyzed'
        video.save()

        messages.success(
            request,
            f'Analysis complete: Video "{video.title}" is {result["verdict"].upper()} '
            f'(Confidence: {result["confidence"]:.1%})'
        )
        return redirect('view_results', video_id=video.id)

    except Exception as e:
        video.status = 'error'
        video.save()
        messages.error(request, f'Detection failed: {str(e)}')
        return redirect('detect_forgery')


def _process_forgery_regions(analysis, prediction_result, video, threshold=0.4, show_heatmap=False):
    """Process and save forgery region detections for fake videos."""

    # Clear existing regions
    analysis.regions.all().delete()

    frames = prediction_result['raw_frames']
    frame_indices = prediction_result['frame_indices']
    frame_predictions = prediction_result['frame_predictions']

    # Find top suspicious frames
    fake_preds = [fp for fp in frame_predictions if fp['prediction'] == 'fake']
    fake_preds.sort(key=lambda x: x['score'], reverse=True)
    top_frames = fake_preds[:8]

    results_dir = analysis.results_dir
    os.makedirs(results_dir, exist_ok=True)
    originals_dir = os.path.join(settings.MEDIA_ROOT, 'results', 'originals')
    annotated_dir = os.path.join(settings.MEDIA_ROOT, 'results', 'annotated')
    os.makedirs(originals_dir, exist_ok=True)
    os.makedirs(annotated_dir, exist_ok=True)

    for fp in top_frames:
        frame_idx = fp['frame_index']
        if frame_idx in frame_indices:
            local_idx = frame_indices.index(frame_idx)
            if local_idx < len(frames):
                frame = frames[local_idx]

                # Detect regions
                regions = detect_forgery_regions(frame, threshold=threshold)

                if regions:
                    # Annotate frame
                    annotated = annotate_frame(frame, regions, show_heatmap=show_heatmap)

                    # Save frames to disk
                    orig_filename = f"orig_{video.id}_{frame_idx}.jpg"
                    anno_filename = f"anno_{video.id}_{frame_idx}.jpg"

                    orig_path = os.path.join(originals_dir, orig_filename)
                    anno_path = os.path.join(annotated_dir, anno_filename)

                    cv2.imwrite(orig_path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                    cv2.imwrite(anno_path, cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR))

                    # Save region to database
                    for region in regions:
                        x, y, bw, bh = region['bbox']
                        ForgeryRegion.objects.create(
                            result=analysis,
                            frame_number=frame_idx,
                            original_frame=f'results/originals/{orig_filename}',
                            annotated_frame=f'results/annotated/{anno_filename}',
                            region_description=region['description'],
                            confidence=region['confidence'],
                            bbox_x=x,
                            bbox_y=y,
                            bbox_width=bw,
                            bbox_height=bh,
                        )

                    # Set the main screenshot for the analysis if not set yet
                    if not analysis.screenshot:
                        analysis.screenshot = f'results/annotated/{anno_filename}'
                        analysis.save()


@login_required
def view_results(request, video_id):
    """Display detection results for a video."""
    video = get_object_or_404(Video, id=video_id, user=request.user)
    analysis = get_object_or_404(AnalysisResult, video=video)
    regions = analysis.regions.all()

    # Group regions by frame number
    frame_regions = {}
    for region in regions:
        fn = region.frame_number
        if fn not in frame_regions:
            frame_regions[fn] = {
                'frame_number': fn,
                'original_frame': region.original_frame,
                'annotated_frame': region.annotated_frame,
                'regions': [],
            }
        frame_regions[fn]['regions'].append(region)

    sorted_frame_regions = sorted(frame_regions.values(), key=lambda x: x['frame_number'])

    # Prepare chart data for frame predictions
    chart_data = {
        'labels': [],
        'scores': [],
        'colors': [],
    }
    for i, fp in enumerate(analysis.frame_predictions[:100]):  # Limit to 100 for chart
        chart_data['labels'].append(f"Frame {i+1}")
        chart_data['scores'].append(fp['score'])
        chart_data['colors'].append('#ff4444' if fp['prediction'] == 'fake' else '#44ff88')

    context = {
        'video': video,
        'analysis': analysis,
        'regions': regions,
        'frame_regions': sorted_frame_regions,
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'detector/results.html', context)


@login_required
def all_results(request):
    """List all analysis results from test videos."""
    results = AnalysisResult.objects.filter(video__video_type='test', video__user=request.user).select_related('video').all()
    context = {
        'results': results,
    }
    return render(request, 'detector/all_results.html', context)


@login_required
@require_POST
def ajax_upload_video(request):
    """Handle asynchronous video uploads from the train page."""
    video_file = request.FILES.get('video_file')
    title = request.POST.get('title')
    label = request.POST.get('label', 'unlabeled')
    video_type = request.POST.get('video_type', 'sample')
    
    if not video_file or not title or label not in ['real', 'fake', 'unlabeled']:
        return JsonResponse({'status': 'error', 'message': 'Invalid data provided.'}, status=400)
    
    if video_type not in ['sample', 'test']:
        video_type = 'sample'
    
    video = Video.objects.create(
        user=request.user,
        title=title,
        video_file=video_file,
        label=label,
        video_type=video_type,
        file_size_mb=video_file.size / (1024 * 1024)
    )
    
    try:
        # Determine specific folder based on label to make it clear
        label_dir = video.label if video.label != 'unlabeled' else 'training'
        output_dir = os.path.join(settings.MEDIA_ROOT, 'frames', label_dir, str(video.id))
        
        # Extract 10 frames for preview and training
        result = extract_frames(video.video_path, output_dir=output_dir, max_frames=10)
        
        video.frame_count = result['total_video_frames']
        video.duration_seconds = result['duration']
        
        # Save a thumbnail
        if result['frames']:
            thumb_name = f"thumb_{video.id}.jpg"
            thumb_path = os.path.join(settings.MEDIA_ROOT, 'thumbnails', thumb_name)
            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
            cv2.imwrite(thumb_path, cv2.cvtColor(result['frames'][0], cv2.COLOR_RGB2BGR))
            video.thumbnail = f"thumbnails/{thumb_name}"
            
        video.save()
    except Exception as e:
        print(f"Frame extraction failed: {str(e)}")
        
    # Get frame URLs for preview
    frame_urls = []
    if os.path.exists(output_dir):
        # Explicit numeric sort to ensure 1, 2, ... 10 order
        files = os.listdir(output_dir)
        # Filter only jpg files and sort by number found in filename
        files = [f for f in files if f.endswith('.jpg')]
        files.sort(key=lambda x: int(re.search(r'(\d+)', x).group(1)) if re.search(r'(\d+)', x) else 0)
        files = files[:10]
        for f in files:
            frame_urls.append(f"{settings.MEDIA_URL}frames/{label_dir}/{video.id}/{f}")

    return JsonResponse({
        'status': 'success', 
        'video_id': video.id, 
        'message': f'Video uploaded successfully!',
        'video': {
            'title': video.title,
            'file_size_mb': f"{video.file_size_mb:.1f}",
            'duration_seconds': f"{video.duration_seconds:.1f}",
            'frame_count': video.frame_count,
            'label': video.label,
            'video_type': video.video_type,
            'status': video.status,
            'thumbnail_url': video.thumbnail.url if video.thumbnail else None,
            'frame_urls': frame_urls,
        }
    })


@login_required
@require_POST
def ajax_train_model(request):
    """Trigger model training asynchronously."""
    real_count = Video.objects.filter(label='real', video_type='sample', user=request.user).count()
    fake_count = Video.objects.filter(label='fake', video_type='sample', user=request.user).count()
    
    if real_count == 0 or fake_count == 0:
        return JsonResponse({'status': 'error', 'message': 'Need at least 1 real AND 1 fake labeled video.'}, status=400)
        
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    session = TrainingSession.objects.create(
        user=request.user,
        epochs=1,
        batch_size=2,
    )
    
    try:
        labeled_videos = Video.objects.filter(video_type='sample', user=request.user).exclude(label='unlabeled')
        
        result = run_training(
            training_session=session,
            videos_queryset=labeled_videos,
            epochs=1,
            batch_size=2,
            validation_split=profile_obj.preferred_validation_split,
        )
        return JsonResponse({'status': 'success', 'message': 'Model is trained!', 'accuracy': result.get('final_accuracy', 0)})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_POST
def ajax_test_video(request):
    """Upload a test video and run predictions immediately."""
    video_file = request.FILES.get('video_file')
    if not video_file:
        return JsonResponse({'status': 'error', 'message': 'No video file provided.'}, status=400)
        
    video = Video.objects.create(
        user=request.user,
        title=request.POST.get('title', 'Test Video'),
        video_file=video_file,
        label='unlabeled',
        video_type='test',
        file_size_mb=video_file.size / (1024 * 1024)
    )
    
    latest_session = TrainingSession.objects.filter(user=request.user, status='completed').first()
    if not latest_session or not latest_session.model_path or not os.path.exists(latest_session.model_path):
        return JsonResponse({'status': 'error', 'message': 'No trained model found.'}, status=400)
    
    model_path = latest_session.model_path
        
    try:
        video.status = 'processing'
        video.save()
        
        profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
        result = predict_video(
            video.video_path,
            model_path,
            max_frames=profile_obj.preferred_frame_sample_rate * 2
        )
        
        analysis, _ = AnalysisResult.objects.update_or_create(
            video=video,
            defaults={
                'verdict': result['verdict'],
                'confidence': result['confidence'],
                'total_frames_analyzed': result['total_frames_analyzed'],
                'fake_frame_count': result['fake_frame_count'],
                'real_frame_count': result['real_frame_count'],
                'frame_predictions': result['frame_predictions'],
                'processing_time_seconds': result['processing_time'],
            }
        )
        
        annotated_frame_url = None
        if result['verdict'] == 'fake':
            profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
            _process_forgery_regions(
                analysis,
                result,
                video,
                threshold=profile_obj.detection_threshold,
                show_heatmap=profile_obj.show_heatmap,
            )
            # Fetch the first region saved
            first_region = analysis.regions.first()
            if first_region and first_region.annotated_frame:
                annotated_frame_url = first_region.annotated_frame.url

        video.status = 'analyzed'
        video.save()
        
        return JsonResponse({
            'status': 'success',
            'verdict': result['verdict'],
            'confidence': result['confidence'],
            'message': f"Video is detected as {result['verdict'].upper()}",
            'annotated_frame_url': annotated_frame_url
        })
    except Exception as e:
        video.status = 'error'
        video.save()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_POST
def ajax_delete_video(request, video_id):
    """Asynchronously delete an uploaded video."""
    video = get_object_or_404(Video, id=video_id, user=request.user)
    
    # Delete video file and frames
    if video.video_file and os.path.exists(video.video_path):
        os.remove(video.video_path)
    if os.path.exists(video.frames_dir):
        import shutil
        shutil.rmtree(video.frames_dir)
        
    video.delete()
    return JsonResponse({'status': 'success', 'message': 'Video deleted.'})


@login_required
@require_POST
def ajax_update_label(request, video_id):
    """Asynchronously update a video's label."""
    video = get_object_or_404(Video, id=video_id, user=request.user)
    new_label = request.POST.get('label', 'unlabeled')
    if new_label in ['real', 'fake', 'unlabeled']:
        video.label = new_label
        video.save()
        return JsonResponse({'status': 'success', 'message': f'Label updated to {new_label}.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid label.'}, status=400)
