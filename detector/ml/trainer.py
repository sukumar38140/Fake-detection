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
                validation_split=0.2):
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
                    result = extract_frames(video_path, output_dir=video.frames_dir, max_frames=10)
                    frames = result['frames']  # Shape: (num_frames, H, W, 3)
                    
                    # Compute simple features from frames
                    features = compute_frame_features(frames)
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
                    result = extract_frames(video_path, output_dir=video.frames_dir, max_frames=10)
                    frames = result['frames']
                    
                    # Compute simple features from frames
                    features = compute_frame_features(frames)
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
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=validation_split, random_state=42, stratify=y if len(np.unique(y)) > 1 else None
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
        os.makedirs(str(model_dir), exist_ok=True)
        model_path = str(getattr(settings, 'MODEL_FILE',
                                 os.path.join(str(model_dir), 'forgeryDetect_model.pkl')))

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


def compute_frame_features(frames):
    """
    Compute simple statistical features from video frames.
    
    Args:
        frames: numpy array of shape (num_frames, H, W, 3)
    
    Returns:
        numpy array of computed features
    """
    features = []
    
    # Compute statistics across all frames
    for frame in frames:
        # Mean color values
        mean_r = np.mean(frame[:, :, 0])
        mean_g = np.mean(frame[:, :, 1])
        mean_b = np.mean(frame[:, :, 2])
        
        # Standard deviation of color values
        std_r = np.std(frame[:, :, 0])
        std_g = np.std(frame[:, :, 1])
        std_b = np.std(frame[:, :, 2])
        
        # Brightness (average intensity)
        brightness = np.mean(frame)
        
        # Contrast (standard deviation of all pixels)
        contrast = np.std(frame)
        
        features.extend([mean_r, mean_g, mean_b, std_r, std_g, std_b, brightness, contrast])
    
    return np.array(features)
