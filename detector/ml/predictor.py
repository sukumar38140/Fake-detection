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


def get_model(model_path):
    """
    Get the trained model.
    """
    if not model_path or not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found. Please train a model first.")
    
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    return model


def predict_video(video_path, model_path=None, max_frames=None):
    """
    Run forgery detection on a video file using RandomForest classifier.

    Args:
        video_path: Path to the video file
        model_path: Path to the trained model
        max_frames: Maximum number of frames to analyze

    Returns:
        dict with prediction results
    """
    start_time = time.time()

    # Step 1: Extract frames
    if max_frames is None:
        max_frames = 10
        
    extraction_result = extract_frames(video_path, max_frames=max_frames)
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
