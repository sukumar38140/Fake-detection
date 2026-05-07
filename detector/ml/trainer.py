"""
Lightweight Model Training Module (Scikit-learn based)
Handles training a simple ML model on labeled video datasets without TensorFlow.
This is a demo/fallback implementation for environments with Windows path constraints.
"""
import os
import json
import pickle
import numpy as np
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from .frame_extractor import extract_frames


def train_model(training_session, videos_queryset, epochs=50, batch_size=16,
                validation_split=0.2, max_frames=10):
    """
    Train a lightweight RandomForest model on labeled videos using scikit-learn.

    Args:
        training_session: TrainingSession model instance
        videos_queryset: Queryset of Video objects with labels
        epochs: Number of epochs (for compatibility, not used in RF)
        batch_size: Batch size (for compatibility, not used in RF)
        validation_split: Fraction of data for validation

    Returns:
        dict with training results
    """
    try:
        # Update session status
        training_session.status = 'training'
        training_session.epochs = epochs
        training_session.batch_size = batch_size
        training_session.save()

        # Separate real and fake videos
        real_videos = videos_queryset.filter(label='real')
        fake_videos = videos_queryset.filter(label='fake')

        if real_videos.count() == 0 or fake_videos.count() == 0:
            raise ValueError(
                "Need at least one real AND one fake labeled video for training. "
                f"Found: {real_videos.count()} real, {fake_videos.count()} fake."
            )

        # Extract frames and compute features
        X_list = []
        y_list = []

        # Process real videos
        for video in real_videos:
            video_path = video.video_path
            if os.path.exists(video_path):
                try:
                    result = extract_frames(video_path, max_frames=max_frames)
                    frames = result['frames']
                    
                    for frame in frames:
                        # Compute features for THIS frame only
                        features = compute_single_frame_features(frame)
                        X_list.append(features)
                        y_list.append(0)  # 0 = real
                except Exception as e:
                    print(f"Warning: Could not process real video {video.id}: {e}")
                    continue

        # Process fake videos
        for video in fake_videos:
            video_path = video.video_path
            if os.path.exists(video_path):
                try:
                    result = extract_frames(video_path, max_frames=max_frames)
                    frames = result['frames']
                    
                    for frame in frames:
                        # Compute features for THIS frame only
                        features = compute_single_frame_features(frame)
                        X_list.append(features)
                        y_list.append(1)  # 1 = fake
                except Exception as e:
                    print(f"Warning: Could not process fake video {video.id}: {e}")
                    continue

        if len(X_list) < 2:
            raise ValueError("Could not extract features from enough videos for training.")

        # Prepare training data
        from sklearn.model_selection import train_test_split
        
        X = np.array(X_list)
        y = np.array(y_list)
        
        # Split data
        test_size = validation_split
        # Only stratify if we have enough samples of each class
        stratify_data = y if (np.sum(y==0) >= 2 and np.sum(y==1) >= 2) else None
        
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=stratify_data
        )

        training_session.total_videos = real_videos.count() + fake_videos.count()
        training_session.total_frames = len(X_train) + len(X_val)
        training_session.save()

        # Build and train model
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)

        # Evaluate model
        train_accuracy = model.score(X_train, y_train)
        val_accuracy = model.score(X_val, y_val) if len(X_val) > 0 else train_accuracy

        # Ensure model directory exists
        model_dir = getattr(settings, 'ML_MODELS_DIR', os.path.join(settings.BASE_DIR, 'ml_models'))
        user_model_dir = os.path.join(str(model_dir), f'user_{training_session.user.id}')
        os.makedirs(user_model_dir, exist_ok=True)
        
        model_filename = f"model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        model_path = os.path.join(user_model_dir, model_filename)

        # Save model
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)

        # Update session
        training_session.status = 'completed'
        training_session.completed_at = timezone.now()
        training_session.model_path = model_path
        training_session.final_accuracy = float(train_accuracy)
        training_session.final_loss = 0.0 # RF doesn't have loss like NN
        training_session.val_accuracy = float(val_accuracy)
        training_session.val_loss = 0.0
        training_session.save()

        return {
            'status': 'completed',
            'model_path': model_path,
            'final_accuracy': training_session.final_accuracy,
            'final_loss': training_session.final_loss,
            'val_accuracy': training_session.val_accuracy,
            'val_loss': training_session.val_loss,
            'model_summary': f"RandomForestClassifier(n_estimators=100) trained on {len(X_train)} samples",
        }

    except Exception as e:
        training_session.status = 'failed'
        training_session.error_message = str(e)
        training_session.completed_at = timezone.now()
        training_session.save()
        raise


def compute_single_frame_features(frame):
    """
    Compute statistical and forensic features from a single frame.
    
    Features:
    - RGB Statistics (Mean, Std)
    - Brightness & Contrast
    - Laplacian Variance (Focus/Blur measure)
    - Basic color histogram (3 bins per channel)
    """
    import cv2
    
    # 1. Basic Statistical Features
    mean_vals = np.mean(frame, axis=(0, 1)) # [R, G, B]
    std_vals = np.std(frame, axis=(0, 1))   # [R, G, B]
    brightness = np.mean(mean_vals)
    contrast = np.mean(std_vals)
    
    # 2. Forensic Features
    # Laplacian Variance: Deepfakes often have inconsistent blur/sharpness
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # 3. Simple Color Histogram (3 bins per channel)
    hist_features = []
    for i in range(3):
        hist = cv2.calcHist([frame], [i], None, [3], [0, 256])
        hist = cv2.normalize(hist, hist).flatten()
        hist_features.extend(hist)
        
    features = [
        *mean_vals,
        *std_vals,
        brightness,
        contrast,
        laplacian_var,
        *hist_features
    ]
    
    return np.array(features)
