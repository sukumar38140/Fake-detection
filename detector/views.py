"""
Views for the Video Forgery Detection System.
Handles dashboard, upload, training, detection, and results visualization.
"""
import os
import time
import json
import traceback

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import Video, AnalysisResult, ForgeryRegion, TrainingSession
from .forms import VideoUploadForm, TrainingConfigForm


def register_user(request):
    """Handle user registration."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
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
        form = UserCreationForm()
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
    sample_videos = Video.objects.filter(video_type='sample')
    total_samples = sample_videos.count()
    real_samples = sample_videos.filter(label='real').count()
    fake_samples = sample_videos.filter(label='fake').count()
    
    # Stats for test videos (used for detection)
    test_videos = Video.objects.filter(video_type='test')
    total_tests = test_videos.count()
    
    # Analysis results from test videos only
    analyzed_tests = AnalysisResult.objects.filter(video__video_type='test').count()
    fake_detected = AnalysisResult.objects.filter(video__video_type='test', verdict='fake').count()
    real_detected = AnalysisResult.objects.filter(video__video_type='test', verdict='real').count()
    
    training_sessions = TrainingSession.objects.count()
    latest_session = TrainingSession.objects.first()

    # Check if model exists
    model_path = str(getattr(settings, 'MODEL_FILE', ''))
    model_exists = os.path.exists(model_path) if model_path else False

    # Get current test video (last uploaded)
    current_test_video = test_videos.order_by('-uploaded_at').first()
    current_result = None
    if current_test_video:
        current_result = AnalysisResult.objects.filter(video=current_test_video).first()

    # Recent analysis results from test videos
    recent_results = AnalysisResult.objects.filter(video__video_type='test').select_related('video').all()[:5]

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
    """Handle video file upload - separated for samples and test videos."""
    if request.method == 'POST':
        form = VideoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            video = form.save(commit=False)

            # Calculate file size
            video_file = request.FILES['video_file']
            video.file_size_mb = video_file.size / (1024 * 1024)
            video.save()

            # Extract video metadata using OpenCV
            try:
                from .ml.frame_extractor import get_video_info
                info = get_video_info(video.video_path)
                video.frame_count = info['total_frames']
                video.duration_seconds = info['duration']
                video.save()
            except Exception:
                pass

            video_type_display = 'Sample' if video.video_type == 'sample' else 'Test'
            messages.success(request, f'{video_type_display} video "{video.title}" uploaded successfully! ({video.file_size_mb:.1f} MB)')
            return redirect('upload_video')
    else:
        video_type = request.GET.get('type', 'sample')
        form = VideoUploadForm(initial={'video_type': video_type})

    # Separate sample and test videos
    sample_videos = Video.objects.filter(video_type='sample')
    test_videos = Video.objects.filter(video_type='test')
    labeled_sample_count = sample_videos.exclude(label='unlabeled').count()

    context = {
        'form': form,
        'sample_videos': sample_videos,
        'test_videos': test_videos,
        'labeled_sample_count': labeled_sample_count,
    }
    return render(request, 'detector/upload.html', context)


@require_POST
@login_required
def delete_video(request, video_id):
    """Delete an uploaded video."""
    video = get_object_or_404(Video, id=video_id)
    title = video.title

    # Delete video file and frames
    if video.video_file and os.path.exists(video.video_path):
        os.remove(video.video_path)
    if os.path.exists(video.frames_dir):
        import shutil
        shutil.rmtree(video.frames_dir)

    video.delete()
    messages.success(request, f'Video "{title}" deleted.')
    return redirect('upload_video')


@require_POST
@login_required
def update_label(request, video_id):
    """Update a video's label (real/fake)."""
    video = get_object_or_404(Video, id=video_id)
    new_label = request.POST.get('label', 'unlabeled')
    if new_label in ['real', 'fake', 'unlabeled']:
        video.label = new_label
        video.save()
        messages.success(request, f'Label for "{video.title}" updated to {new_label}.')
    return redirect('upload_video')


@login_required
def train_model(request):
    """Model training page and handler."""
    if request.method == 'POST':
        form = TrainingConfigForm(request.POST)
        if form.is_valid():
            epochs = form.cleaned_data['epochs']
            batch_size = form.cleaned_data['batch_size']
            validation_split = form.cleaned_data['validation_split']

            # Check for labeled sample videos
            real_count = Video.objects.filter(label='real', video_type='sample').count()
            fake_count = Video.objects.filter(label='fake', video_type='sample').count()

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
                epochs=epochs,
                batch_size=batch_size,
            )

            # Run training
            try:
                from .ml.trainer import train_model as run_training
                labeled_videos = Video.objects.filter(video_type='sample').exclude(label='unlabeled')

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
    sessions = TrainingSession.objects.all()[:10]
    model_path = str(getattr(settings, 'MODEL_FILE', ''))
    model_exists = os.path.exists(model_path) if model_path else False

    # Dataset stats for sample videos
    real_count = Video.objects.filter(label='real', video_type='sample').count()
    fake_count = Video.objects.filter(label='fake', video_type='sample').count()
    total_labeled = real_count + fake_count

    context = {
        'form': form,
        'sessions': sessions,
        'model_exists': model_exists,
        'real_count': real_count,
        'fake_count': fake_count,
        'total_labeled': total_labeled,
    }
    return render(request, 'detector/train.html', context)


@login_required
def detect_forgery(request):
    """Video forgery detection page - show only test video if exists."""
    # Get the current test video (last uploaded test video)
    test_video = Video.objects.filter(video_type='test').order_by('-uploaded_at').first()
    
    model_path = str(getattr(settings, 'MODEL_FILE', ''))
    model_exists = os.path.exists(model_path) if model_path else False

    context = {
        'video': test_video,
        'model_exists': model_exists,
    }
    return render(request, 'detector/detect.html', context)


@login_required
def run_detection(request, video_id):
    """Run forgery detection on a specific video."""
    video = get_object_or_404(Video, id=video_id)

    model_path = str(getattr(settings, 'MODEL_FILE', ''))
    if not os.path.exists(model_path):
        messages.error(request, 'No trained model found. Please train a model first.')
        return redirect('detect_forgery')

    try:
        video.status = 'processing'
        video.save()

        # Run prediction
        from .ml.predictor import predict_video
        result = predict_video(video.video_path, model_path)

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
            _process_forgery_regions(analysis, result, video)

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


def _process_forgery_regions(analysis, prediction_result, video):
    """Process and save forgery region detections for fake videos."""
    import cv2
    from .ml.region_detector import detect_forgery_regions, annotate_frame

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
                regions = detect_forgery_regions(frame, threshold=0.3)

                if regions:
                    # Annotate frame
                    annotated = annotate_frame(frame, regions)

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
    video = get_object_or_404(Video, id=video_id)
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
    results = AnalysisResult.objects.filter(video__video_type='test').select_related('video').all()
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
        title=title,
        video_file=video_file,
        label=label,
        video_type=video_type,
        file_size_mb=video_file.size / (1024 * 1024)
    )
    
    try:
        from .ml.frame_extractor import extract_frames
        import cv2
        
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
        import re
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
    real_count = Video.objects.filter(label='real', video_type='sample').count()
    fake_count = Video.objects.filter(label='fake', video_type='sample').count()
    
    if real_count == 0 or fake_count == 0:
        return JsonResponse({'status': 'error', 'message': 'Need at least 1 real AND 1 fake labeled video.'}, status=400)
        
    session = TrainingSession.objects.create(
        epochs=1,  # Short epochs for demonstration purposes
        batch_size=2,
    )
    
    try:
        from .ml.trainer import train_model as run_training
        labeled_videos = Video.objects.filter(video_type='sample').exclude(label='unlabeled')
        
        result = run_training(
            training_session=session,
            videos_queryset=labeled_videos,
            epochs=1,
            batch_size=2,
            validation_split=0.2,
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
        title=request.POST.get('title', 'Test Video'),
        video_file=video_file,
        label='unlabeled',
        video_type='test',
        file_size_mb=video_file.size / (1024 * 1024)
    )
    
    model_path = str(getattr(settings, 'MODEL_FILE', ''))
    if not os.path.exists(model_path):
        return JsonResponse({'status': 'error', 'message': 'No trained model found.'}, status=400)
        
    try:
        video.status = 'processing'
        video.save()
        
        from .ml.predictor import predict_video
        result = predict_video(video.video_path, model_path)
        
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
            _process_forgery_regions(analysis, result, video)
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
    video = get_object_or_404(Video, id=video_id)
    
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
    video = get_object_or_404(Video, id=video_id)
    new_label = request.POST.get('label', 'unlabeled')
    if new_label in ['real', 'fake', 'unlabeled']:
        video.label = new_label
        video.save()
        return JsonResponse({'status': 'success', 'message': f'Label updated to {new_label}.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid label.'}, status=400)
