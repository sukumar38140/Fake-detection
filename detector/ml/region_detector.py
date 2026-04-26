"""
Forgery Region Detection Module
Uses Grad-CAM (Gradient-weighted Class Activation Mapping) and Error Level Analysis
to detect and highlight manipulated regions in video frames.

This combines:
1. Grad-CAM: Highlights regions that most influenced the "fake" prediction
2. ELA (Error Level Analysis): Detects compression-level inconsistencies
3. Edge Analysis: Identifies splicing boundaries

Output: Annotated frames with red bounding boxes around suspicious regions.
"""
import os

import cv2
import numpy as np
from django.conf import settings

def compute_gradcam_heatmap(model, input_sequence, class_index=0):
    """
    Compute Grad-CAM heatmap for the last convolutional layer.
    (Disabled/Dummy implementation because tensorflow is removed)
    """
    seq_len = input_sequence.shape[1] if hasattr(input_sequence, 'shape') and len(input_sequence.shape) > 1 else 10
    frame_size = input_sequence.shape[2:4] if hasattr(input_sequence, 'shape') and len(input_sequence.shape) > 3 else (128, 128)
    return [np.ones(frame_size, dtype=np.float32) * 0.5] * seq_len



def error_level_analysis(frame, quality=90):
    """
    Perform Error Level Analysis (ELA) on a frame.
    ELA detects compression-level inconsistencies that indicate manipulation.

    Args:
        frame: Input frame (BGR)
        quality: JPEG recompression quality

    Returns:
        ELA difference image (grayscale, normalized 0-1)
    """
    # Re-compress at specified quality
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    _, encoded = cv2.imencode('.jpg', frame, encode_param)
    recompressed = cv2.imdecode(encoded, cv2.IMREAD_COLOR)

    # Compute absolute difference
    diff = cv2.absdiff(frame, recompressed)

    # Convert to grayscale and amplify
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    gray_diff = gray_diff.astype(np.float32)

    # Amplify differences
    gray_diff *= 10.0
    gray_diff = np.clip(gray_diff, 0, 255)

    # Normalize to 0-1
    if gray_diff.max() > 0:
        gray_diff = gray_diff / gray_diff.max()

    return gray_diff


def detect_edge_inconsistencies(frame):
    """
    Detect edge inconsistencies that may indicate splicing.

    Args:
        frame: Input frame (BGR)

    Returns:
        Edge anomaly map (grayscale, normalized 0-1)
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Multi-scale edge detection
    edges_low = cv2.Canny(gray, 30, 80)
    edges_high = cv2.Canny(gray, 100, 200)

    # Difference between multi-scale edges indicates anomalies
    edge_diff = cv2.absdiff(edges_low, edges_high)

    # Dilate to connect nearby edges
    kernel = np.ones((5, 5), np.uint8)
    edge_diff = cv2.dilate(edge_diff, kernel, iterations=2)

    # Apply Gaussian blur
    edge_diff = cv2.GaussianBlur(edge_diff.astype(np.float32), (21, 21), 0)

    # Normalize
    if edge_diff.max() > 0:
        edge_diff = edge_diff / edge_diff.max()

    return edge_diff


def detect_forgery_regions(frame, heatmap=None, threshold=0.4, min_area=500):
    """
    Detect and localize forged regions in a frame.

    Combines:
    - Grad-CAM heatmap (model attention)
    - ELA (compression analysis)
    - Edge inconsistencies

    Args:
        frame: Original frame (RGB)
        heatmap: Grad-CAM heatmap (optional)
        threshold: Detection threshold
        min_area: Minimum region area in pixels

    Returns:
        List of detected regions with bounding boxes
    """
    # Convert RGB to BGR for OpenCV operations
    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    h, w = frame_bgr.shape[:2]

    # Compute ELA
    ela_map = error_level_analysis(frame_bgr)
    ela_resized = cv2.resize(ela_map, (w, h))

    # Compute edge map
    edge_map = detect_edge_inconsistencies(frame_bgr)
    edge_resized = cv2.resize(edge_map, (w, h))

    # Combine analysis maps
    if heatmap is not None:
        heatmap_resized = cv2.resize(heatmap, (w, h))
        # Weighted combination: Grad-CAM (0.5) + ELA (0.3) + Edge (0.2)
        combined = (0.5 * heatmap_resized + 0.3 * ela_resized + 0.2 * edge_resized)
    else:
        combined = (0.6 * ela_resized + 0.4 * edge_resized)

    # Normalize combined map
    if combined.max() > 0:
        combined = combined / combined.max()

    # Threshold to get binary mask
    binary = (combined > threshold).astype(np.uint8) * 255

    # Morphological operations to clean up
    kernel = np.ones((7, 7), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    # Find contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    regions = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area >= min_area:
            x, y, bw, bh = cv2.boundingRect(contour)
            # Calculate region confidence from the combined map
            region_mask = np.zeros_like(combined)
            cv2.drawContours(region_mask, [contour], -1, 1, -1)
            region_confidence = float(np.mean(combined[region_mask > 0]))

            regions.append({
                'bbox': (x, y, bw, bh),
                'confidence': region_confidence,
                'area': area,
                'description': classify_region(x, y, bw, bh, w, h),
            })

    # Sort by confidence (most suspicious first)
    regions.sort(key=lambda r: r['confidence'], reverse=True)

    # Limit to top 5 regions
    return regions[:5]


def classify_region(x, y, w, h, frame_w, frame_h):
    """
    Classify the suspicious region based on its location in the frame.

    Args:
        x, y, w, h: Bounding box
        frame_w, frame_h: Frame dimensions

    Returns:
        Description string
    """
    cx = x + w / 2
    cy = y + h / 2

    # Check if centered (likely face/object)
    if 0.25 * frame_w < cx < 0.75 * frame_w and 0.15 * frame_h < cy < 0.6 * frame_h:
        if w * h > 0.1 * frame_w * frame_h:
            return "Face/Object Region"
        else:
            return "Suspicious Detail"
    elif cy < 0.3 * frame_h:
        return "Background Region (Top)"
    elif cy > 0.7 * frame_h:
        return "Background Region (Bottom)"
    elif cx < 0.3 * frame_w:
        return "Peripheral Region (Left)"
    elif cx > 0.7 * frame_w:
        return "Peripheral Region (Right)"
    else:
        return "Suspicious Region"


def annotate_frame(frame, regions, show_heatmap=False, heatmap=None):
    """
    Draw bounding boxes and labels on a frame to highlight forged regions.

    Args:
        frame: Original frame (RGB)
        regions: List of detected regions from detect_forgery_regions
        show_heatmap: Whether to overlay the heatmap
        heatmap: Optional heatmap to overlay

    Returns:
        Annotated frame (RGB)
    """
    annotated = frame.copy()

    if show_heatmap and heatmap is not None:
        # Create colored heatmap overlay
        h, w = frame.shape[:2]
        heatmap_resized = cv2.resize(heatmap, (w, h))
        heatmap_colored = cv2.applyColorMap(
            (heatmap_resized * 255).astype(np.uint8),
            cv2.COLORMAP_JET
        )
        heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)
        annotated = cv2.addWeighted(annotated, 0.6, heatmap_colored, 0.4, 0)

    for region in regions:
        x, y, bw, bh = region['bbox']
        confidence = region['confidence']
        description = region['description']

        # Red bounding box
        color = (255, 40, 40)
        thickness = 3

        # Draw rectangle
        cv2.rectangle(annotated, (x, y), (x + bw, y + bh), color, thickness)

        # Draw label background
        label = f"{description} ({confidence:.0%})"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, 1)

        # Label background
        cv2.rectangle(annotated, (x, y - text_h - 10), (x + text_w + 4, y), (255, 40, 40), -1)

        # Label text (white on red)
        cv2.putText(annotated, label, (x + 2, y - 5), font, font_scale, (255, 255, 255), 1)

    return annotated


def process_fake_video_regions(frames, frame_indices, model, prediction_results):
    """
    Process a video detected as fake: find and annotate forged regions.

    Args:
        frames: List of raw frames (RGB)
        frame_indices: Original frame indices from the video
        model: Trained model for Grad-CAM
        prediction_results: Frame prediction results

    Returns:
        List of dicts with annotated frame data
    """
    results = []
    seq_length = getattr(settings, 'SEQUENCE_LENGTH', 15)
    frame_size = getattr(settings, 'FRAME_SIZE', (128, 128))

    # Find the most suspicious frames
    fake_predictions = [
        fp for fp in prediction_results
        if fp['prediction'] == 'fake'
    ]

    # Sort by score (highest suspicion first) and take top frames
    fake_predictions.sort(key=lambda x: x['score'], reverse=True)
    top_suspicious = fake_predictions[:10]

    for fp in top_suspicious:
        frame_idx = fp['frame_index']

        # Find this frame in our extracted frames
        if frame_idx in frame_indices:
            local_idx = frame_indices.index(frame_idx)
            if local_idx < len(frames):
                frame = frames[local_idx]

                # Detect forgery regions
                regions = detect_forgery_regions(frame, threshold=0.3)

                if regions:
                    # Annotate the frame
                    annotated = annotate_frame(frame, regions)

                    results.append({
                        'frame_number': frame_idx,
                        'original_frame': frame,
                        'annotated_frame': annotated,
                        'regions': regions,
                        'score': fp['score'],
                    })

    return results
