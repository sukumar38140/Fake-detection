"""
DCNN + LSTM Model Architecture
Model Architecture Builder
(Disabled/Dummy implementation because tensorflow is removed)
"""

import os
from django.conf import settings


def build_dcnn_lstm_model(input_shape=(15, 128, 128, 3), num_classes=2):
    raise NotImplementedError("TensorFlow has been removed. Use the RandomForest fallback.")


def build_feature_extractor(model):
    """
    Build a feature extractor from the trained model for Grad-CAM.
    Extracts the last convolutional layer's output.

    Args:
        model: Trained DCNN-LSTM model

    Returns:
        Feature extractor model
    """
    raise NotImplementedError("TensorFlow has been removed.")


def get_model_summary(model):
    return "RandomForest Classifier (TensorFlow removed)"


def load_model(model_path=None):
    """
    Load a previously saved model.

    Args:
        model_path: Path to the .h5 model file

    Returns:
        Loaded Keras model
    """
    if model_path is None:
        model_path = str(getattr(settings, 'MODEL_FILE', 'ml_models/forgeryDetect_model.h5'))

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")

    raise NotImplementedError("TensorFlow has been removed. Use pickle to load the RandomForest model.")
