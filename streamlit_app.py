import streamlit as st
import os
import cv2
import tempfile
import numpy as np
from PIL import Image
import time

# Mock Django settings for standalone use
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'forgery_project.settings'
    import django
    django.setup()

from detector.ml.predictor import predict_video
from detector.ml.region_detector import detect_forgery_regions, annotate_frame

# Page config
st.set_page_config(
    page_title="DeepFake Detection Forensic Tool",
    page_icon="🔍",
    layout="wide"
)

# Custom CSS for premium look
st.markdown("""
    <style>
    .main {
        background-color: #0f172a;
        color: #f8fafc;
    }
    .stAlert {
        border-radius: 10px;
    }
    .verdict-fake {
        color: #ef4444;
        font-size: 24px;
        font-weight: bold;
    }
    .verdict-real {
        color: #22c55e;
        font-size: 24px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_value=True)

st.title("🔍 DeepFake Detection Forensic Tool")
st.markdown("---")

# Sidebar
st.sidebar.header("Settings")
confidence_threshold = st.sidebar.slider("Sensitivity Threshold", 0.1, 0.9, 0.5)

# File Uploader
uploaded_file = st.file_uploader("Upload a video for forensic analysis", type=['mp4', 'avi', 'mov', 'mkv'])

if uploaded_file is not None:
    # Save uploaded file to a temporary location
    tfile = tempfile.NamedTemporaryFile(delete=False)
    tfile.write(uploaded_file.read())
    video_path = tfile.name

    st.info("🔄 Running Forensic Analysis... This may take a moment.")
    
    # Progress bar
    progress_bar = st.progress(0)
    for i in range(50):
        time.sleep(0.01)
        progress_bar.progress(i + 1)

    try:
        # Run detection
        results = predict_video(video_path)
        
        progress_bar.progress(100)
        
        # Display Results Header
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Video Preview")
            st.video(uploaded_file)
            
        with col2:
            st.subheader("Analysis Summary")
            verdict = results['verdict']
            confidence = results['confidence']
            
            if verdict == 'fake':
                st.markdown(f"Verdict: <span class='verdict-fake'>FORGERY DETECTED</span>", unsafe_allow_value=True)
                st.error(f"Confidence: {confidence:.2%}")
            else:
                st.markdown(f"Verdict: <span class='verdict-real'>AUTHENTIC / REAL</span>", unsafe_allow_value=True)
                st.success(f"Confidence: {confidence:.2%}")
                
            st.write(f"Frames Analyzed: {results['total_frames_analyzed']}")
            st.write(f"Processing Time: {results['processing_time']:.2f}s")

        # Frame by Frame Analysis
        st.markdown("---")
        st.subheader("📊 Forensic Evidence (Frame-by-Frame)")
        
        # Plot score chart
        scores = [f['score'] for f in results['frame_predictions']]
        st.area_chart(scores)
        
        # Show Suspicious Frames
        if verdict == 'fake':
            st.subheader("🚩 Suspicious Regions Detected")
            
            # Find frames with highest scores
            suspicious_preds = [f for f in results['frame_predictions'] if f['score'] > confidence_threshold]
            suspicious_preds.sort(key=lambda x: x['score'], reverse=True)
            
            if suspicious_preds:
                cols = st.columns(3)
                for i, pred in enumerate(suspicious_preds[:6]): # Show top 6
                    with cols[i % 3]:
                        frame_idx = pred['frame_index']
                        # Get frame image (using existing extractor logic)
                        from detector.ml.frame_extractor import extract_single_frame
                        frame_img = extract_single_frame(video_path, frame_idx)
                        
                        # Detect regions for this frame
                        regions = detect_forgery_regions(frame_img)
                        if regions:
                            annotated = annotate_frame(frame_img, regions)
                            st.image(annotated, caption=f"Frame #{frame_idx} - Score: {pred['score']:.2%}")
                        else:
                            st.image(frame_img, caption=f"Frame #{frame_idx} - Score: {pred['score']:.2%}")
            else:
                st.warning("No specific forgery regions could be localized, but the overall sequence is suspicious.")

    except Exception as e:
        st.error(f"An error occurred during analysis: {str(e)}")
    finally:
        # Cleanup
        os.unlink(video_path)

else:
    st.write("Please upload a video file to begin.")
    
    # Feature highlights
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("🛡️ **Anti-Tamper**\nDetects splicing, cloning, and copy-move attacks.")
    with col2:
        st.info("🧠 **AI Driven**\nUses RandomForest & DCNN features for high accuracy.")
    with col3:
        st.info("📍 **Localization**\nHighlights exactly where the video was modified.")
