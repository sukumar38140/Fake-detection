"""
Prediction / Inference Module
Runs forgery detection on uploaded videos using the trained RandomForest model.
"""
import os
import time
import pickle

import numpy as np
from django.conf import settings

from .frame_extractor import extract_frames
from .trainer import compute_frame_features


# Global model cache to avoid reloading on every request
_cached_model = None
_cached_model_path = None


def get_model(model_path=None):
    """
    Get the trained model (cached for performance).

    Args:
        model_path: Path to the model file

    Returns:
        Loaded scikit-learn model
    """
    global _cached_model, _cached_model_path

    if model_path is None:
        model_dir = getattr(settings, 'ML_MODELS_DIR', os.path.join(settings.BASE_DIR, 'ml_models'))
        model_path = str(getattr(settings, 'MODEL_FILE', os.path.join(str(model_dir), 'forgeryDetect_model.pkl')))

    if _cached_model is None or _cached_model_path != model_path:
        with open(model_path, 'rb') as f:
            _cached_model = pickle.load(f)
        _cached_model_path = model_path

    return _cached_model


def predict_video(video_path, model_path=None):
    """
    Run forgery detection on a video file using RandomForest classifier.

    Process:
    1. Extract frames from video
    2. Compute statistical features from frames
    3. Run RandomForest prediction
    4. Return verdict with confidence

    Args:
        video_path: Path to the video file
        model_path: Path to the trained model

    Returns:
        dict with prediction results
    """
    start_time = time.time()

    # Step 1: Extract frames
    extraction_result = extract_frames(video_path, max_frames=10)
    frames = extraction_result['frames']

    if len(frames) == 0:
        raise ValueError("No frames could be extracted from the video.")

    # Step 2: Compute features
    features = compute_frame_features(frames)

    # Step 3: Load model and predict
    model = get_model(model_path)
    # The model expects a 2D array, so we wrap features in a list
    prediction_proba = model.predict_proba([features])[0]
    prediction = model.predict([features])[0]

    # Step 4: Determine verdict
    if prediction == 1:  # fake
        verdict = 'fake'
        confidence = float(prediction_proba[1])
    else:  # real
        verdict = 'real'
        confidence = float(prediction_proba[0])

    processing_time = time.time() - start_time

    # Create frame-level predictions
    frame_predictions = []
    frame_indices = extraction_result['frame_indices']
    
    # Consistency for the chart: score should be probability of being 'fake'
    forgery_score = float(prediction_proba[1])
    
    for i, frame_idx in enumerate(frame_indices):
        # Distribute the prediction across frames
        frame_predictions.append({
            'frame_index': frame_idx,
            'prediction': 'fake' if forgery_score > 0.5 else 'real',
            'score': forgery_score,
        })

    return {
        'verdict': verdict,
        'confidence': confidence,
        'avg_score': confidence,
        'total_frames_analyzed': len(frame_predictions),
        'fake_frame_count': len(frame_predictions) if verdict == 'fake' else 0,
        'real_frame_count': len(frame_predictions) if verdict == 'real' else 0,
        'frame_predictions': frame_predictions,
        'sequence_predictions': [],  # Not applicable for RF
        'processing_time': processing_time,
        'raw_frames': frames,
        'frame_indices': frame_indices,
    }


def predict_single_frame(frame, model_path=None):
    """
    Predict on a single frame (for debugging/visualization).
    Not implemented for RandomForest model as it expects video-level features.
    """
    raise NotImplementedError("Single frame prediction not supported with RandomForest model.")
