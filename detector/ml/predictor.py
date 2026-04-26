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
from .trainer import compute_single_frame_features


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
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at {model_path}. Please train a model first.")
        with open(model_path, 'rb') as f:
            _cached_model = pickle.load(f)
        _cached_model_path = model_path

    return _cached_model


def predict_video(video_path, model_path=None):
    """
    Run forgery detection on a video file using RandomForest classifier.

    Process:
    1. Extract frames from video
    2. Compute features for EACH frame
    3. Run RandomForest prediction on each frame
    4. Average the results for a final verdict

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
    frame_indices = extraction_result['frame_indices']

    if len(frames) == 0:
        raise ValueError("No frames could be extracted from the video.")

    # Step 2: Load model
    model = get_model(model_path)

    # Step 3: Compute features and predict for each frame
    frame_predictions = []
    
    for i, frame in enumerate(frames):
        features = compute_single_frame_features(frame)
        # Get probability of 'fake' (class 1)
        # model.predict_proba returns [[prob_real, prob_fake]]
        probs = model.predict_proba([features])[0]
        prob_fake = float(probs[1])
        
        frame_predictions.append({
            'frame_index': frame_indices[i],
            'score': prob_fake,
            'prediction': 'fake' if prob_fake > 0.5 else 'real'
        })

    # Step 4: Aggregate results
    avg_fake_score = sum(p['score'] for p in frame_predictions) / len(frame_predictions)
    
    verdict = 'fake' if avg_fake_score > 0.5 else 'real'
    # Confidence is the probability of the chosen verdict
    confidence = avg_fake_score if verdict == 'fake' else (1 - avg_fake_score)
    
    processing_time = time.time() - start_time

    return {
        'verdict': verdict,
        'confidence': confidence,
        'avg_score': avg_fake_score,
        'total_frames_analyzed': len(frame_predictions),
        'fake_frame_count': sum(1 for p in frame_predictions if p['prediction'] == 'fake'),
        'real_frame_count': sum(1 for p in frame_predictions if p['prediction'] == 'real'),
        'frame_predictions': frame_predictions,
        'sequence_predictions': [],  # Not used in RF
        'processing_time': processing_time,
        'raw_frames': frames,
        'frame_indices': frame_indices,
    }


def predict_single_frame(frame, model_path=None):
    """
    Predict on a single frame (for debugging/visualization).
    """
    model = get_model(model_path)
    features = compute_single_frame_features(frame)
    probs = model.predict_proba([features])[0]
    return {
        'verdict': 'fake' if probs[1] > 0.5 else 'real',
        'confidence': float(max(probs)),
        'score': float(probs[1])
    }
