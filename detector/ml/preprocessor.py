"""
Data Preprocessing Module
Handles frame resizing, normalization, sequence creation, and dataset splitting.
"""
import numpy as np
from sklearn.model_selection import train_test_split
from django.conf import settings


def resize_frames(frames, target_size=None):
    """
    Resize frames to target dimensions.

    Args:
        frames: List of numpy arrays (H, W, 3)
        target_size: Tuple (height, width), defaults to settings.FRAME_SIZE

    Returns:
        numpy array of resized frames (N, H, W, 3)
    """
    import cv2

    if target_size is None:
        target_size = getattr(settings, 'FRAME_SIZE', (128, 128))

    resized = []
    for frame in frames:
        resized_frame = cv2.resize(frame, (target_size[1], target_size[0]))
        resized.append(resized_frame)

    return np.array(resized)


def normalize_frames(frames):
    """
    Normalize pixel values from 0-255 to 0-1.

    Args:
        frames: numpy array of frames

    Returns:
        Normalized numpy array (float32)
    """
    return frames.astype(np.float32) / 255.0


def create_sequences(frames, sequence_length=None):
    """
    Group frames into overlapping sequences for LSTM input.

    Args:
        frames: numpy array of preprocessed frames (N, H, W, 3)
        sequence_length: Number of frames per sequence

    Returns:
        numpy array of shape (num_sequences, sequence_length, H, W, 3)
    """
    if sequence_length is None:
        sequence_length = getattr(settings, 'SEQUENCE_LENGTH', 15)

    num_frames = len(frames)
    if num_frames < sequence_length:
        # Pad with repeated last frame if not enough frames
        padding = np.repeat(frames[-1:], sequence_length - num_frames, axis=0)
        frames = np.concatenate([frames, padding], axis=0)
        num_frames = len(frames)

    sequences = []
    stride = max(1, sequence_length // 2)  # 50% overlap

    for i in range(0, num_frames - sequence_length + 1, stride):
        seq = frames[i:i + sequence_length]
        sequences.append(seq)

    # Always include the last sequence
    if len(sequences) == 0 or (num_frames - sequence_length) % stride != 0:
        sequences.append(frames[-sequence_length:])

    return np.array(sequences)


def preprocess_frames(frames, target_size=None, sequence_length=None):
    """
    Full preprocessing pipeline: resize → normalize → create sequences.

    Args:
        frames: List of raw frame numpy arrays
        target_size: Resize target
        sequence_length: LSTM sequence length

    Returns:
        numpy array ready for model input (num_seq, seq_len, H, W, 3)
    """
    # Resize
    resized = resize_frames(frames, target_size)

    # Normalize
    normalized = normalize_frames(resized)

    # Create sequences
    sequences = create_sequences(normalized, sequence_length)

    return sequences


def prepare_training_data(real_frames_list, fake_frames_list, target_size=None,
                          sequence_length=None, validation_split=0.2):
    """
    Prepare training and validation datasets from lists of real and fake video frames.

    Args:
        real_frames_list: List of frame arrays from real videos
        fake_frames_list: List of frame arrays from fake videos
        target_size: Resize target
        sequence_length: LSTM sequence length
        validation_split: Fraction of data for validation

    Returns:
        (X_train, X_val, y_train, y_val)
    """
    all_sequences = []
    all_labels = []

    # Process real videos (label = 0)
    for frames in real_frames_list:
        sequences = preprocess_frames(frames, target_size, sequence_length)
        all_sequences.append(sequences)
        all_labels.extend([0] * len(sequences))

    # Process fake videos (label = 1)
    for frames in fake_frames_list:
        sequences = preprocess_frames(frames, target_size, sequence_length)
        all_sequences.append(sequences)
        all_labels.extend([1] * len(sequences))

    X = np.concatenate(all_sequences, axis=0)
    y = np.array(all_labels, dtype=np.float32)

    # Split into training and validation sets
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=validation_split, random_state=42, stratify=y
    )

    return X_train, X_val, y_train, y_val
