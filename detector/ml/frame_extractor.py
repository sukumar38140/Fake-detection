"""
Frame Extraction Module
Converts videos into frames using OpenCV.
Supports frame sampling for large videos to reduce processing time.
"""
import os
import cv2
import numpy as np
from django.conf import settings


def extract_frames(video_path, output_dir=None, sample_rate=None, max_frames=500):
    """
    Extract frames from a video file using OpenCV.

    Args:
        video_path: Path to the video file
        output_dir: Directory to save extracted frames (optional)
        sample_rate: Extract every Nth frame (None = use settings default)
        max_frames: Maximum number of frames to extract

    Returns:
        dict with keys: frames (list of numpy arrays), frame_count, fps, duration, frame_indices
    """
    if sample_rate is None:
        sample_rate = getattr(settings, 'FRAME_SAMPLE_RATE', 5)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_path}")

    # Get video properties
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / fps if fps > 0 else 0

    # Adjust sample rate for very large videos
    estimated_frames = total_frames // sample_rate
    if estimated_frames > max_frames:
        sample_rate = max(1, total_frames // max_frames)

    frames = []
    frame_indices = []
    frame_idx = 0

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % sample_rate == 0:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(frame_rgb)
            frame_indices.append(frame_idx)

            # Save frame to disk if output_dir specified
            if output_dir:
                frame_path = os.path.join(output_dir, f"frame_{frame_idx:06d}.jpg")
                cv2.imwrite(frame_path, frame)

            if len(frames) >= max_frames:
                break

        frame_idx += 1

    cap.release()

    return {
        'frames': frames,
        'frame_count': len(frames),
        'total_video_frames': total_frames,
        'fps': fps,
        'duration': duration,
        'frame_indices': frame_indices,
        'sample_rate': sample_rate,
    }


def get_video_info(video_path):
    """
    Get basic video information without extracting frames.

    Args:
        video_path: Path to the video file

    Returns:
        dict with video metadata
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_path}")

    info = {
        'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        'fps': cap.get(cv2.CAP_PROP_FPS),
        'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }
    info['duration'] = info['total_frames'] / info['fps'] if info['fps'] > 0 else 0

    cap.release()
    return info


def extract_single_frame(video_path, frame_number):
    """
    Extract a single frame from a video.

    Args:
        video_path: Path to the video file
        frame_number: Frame index to extract

    Returns:
        numpy array of the frame (RGB)
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_path}")

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise ValueError(f"Cannot read frame {frame_number}")

    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
