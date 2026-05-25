import os
import shutil
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.conf import settings
from .models import Video, AnalysisResult, ForgeryRegion
from .views import _delete_video_files

User = get_user_model()

class VideoDeletionTestCase(TestCase):
    def setUp(self):
        self.media_root = settings.MEDIA_ROOT
        os.makedirs(self.media_root, exist_ok=True)
        
        self.user = User.objects.create_user(username='testuser', password='password')
        
        # Create dummy media files
        self.video_file_path = os.path.join(self.media_root, 'dummy_video.mp4')
        with open(self.video_file_path, 'wb') as f:
            f.write(b'video content')
            
        self.thumbnail_path = os.path.join(self.media_root, 'dummy_thumb.jpg')
        with open(self.thumbnail_path, 'wb') as f:
            f.write(b'thumbnail content')
            
        self.screenshot_path = os.path.join(self.media_root, 'dummy_screenshot.jpg')
        with open(self.screenshot_path, 'wb') as f:
            f.write(b'screenshot content')
            
        self.orig_frame_path = os.path.join(self.media_root, 'dummy_orig.jpg')
        with open(self.orig_frame_path, 'wb') as f:
            f.write(b'original frame content')
            
        self.anno_frame_path = os.path.join(self.media_root, 'dummy_anno.jpg')
        with open(self.anno_frame_path, 'wb') as f:
            f.write(b'annotated frame content')

        # Create model objects
        self.video = Video.objects.create(
            user=self.user,
            title="Test Video Deletion",
            video_file='dummy_video.mp4',
            thumbnail='dummy_thumb.jpg',
            status='analyzed',
            label='fake',
            video_type='test'
        )
        
        # Create frames directory
        os.makedirs(self.video.frames_dir, exist_ok=True)
        self.dummy_frame_in_dir = os.path.join(self.video.frames_dir, 'frame_1.jpg')
        with open(self.dummy_frame_in_dir, 'wb') as f:
            f.write(b'extracted frame')
            
        self.analysis = AnalysisResult.objects.create(
            video=self.video,
            verdict='fake',
            confidence=0.9,
            screenshot='dummy_screenshot.jpg'
        )
        
        self.region = ForgeryRegion.objects.create(
            result=self.analysis,
            frame_number=1,
            original_frame='dummy_orig.jpg',
            annotated_frame='dummy_anno.jpg',
            confidence=0.85
        )

    def test_delete_video_files_and_db(self):
        # Verify files exist before deletion
        self.assertTrue(os.path.exists(self.video_file_path))
        self.assertTrue(os.path.exists(self.thumbnail_path))
        self.assertTrue(os.path.exists(self.screenshot_path))
        self.assertTrue(os.path.exists(self.orig_frame_path))
        self.assertTrue(os.path.exists(self.anno_frame_path))
        self.assertTrue(os.path.exists(self.dummy_frame_in_dir))
        
        # Call deletion helper
        _delete_video_files(self.video)
        
        # Verify files are deleted from disk
        self.assertFalse(os.path.exists(self.video_file_path))
        self.assertFalse(os.path.exists(self.thumbnail_path))
        self.assertFalse(os.path.exists(self.screenshot_path))
        self.assertFalse(os.path.exists(self.orig_frame_path))
        self.assertFalse(os.path.exists(self.anno_frame_path))
        self.assertFalse(os.path.exists(self.dummy_frame_in_dir))
        self.assertFalse(os.path.exists(self.video.frames_dir))
        
        # Call database deletion
        video_id = self.video.id
        self.video.delete()
        
        # Verify database records are cascade deleted
        self.assertFalse(Video.objects.filter(id=video_id).exists())
        self.assertFalse(AnalysisResult.objects.filter(video_id=video_id).exists())
        self.assertFalse(ForgeryRegion.objects.filter(result__video_id=video_id).exists())

    def test_ajax_upload_video_empty_title(self):
        from django.urls import reverse
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        self.client.force_login(self.user)
        
        # Test case 1: Upload with empty title
        video_file = SimpleUploadedFile("test_fallback_name.mp4", b"dummy_content", content_type="video/mp4")
        response = self.client.post(
            reverse('ajax_upload_video'),
            {
                'video_file': video_file,
                'title': '',
                'label': 'unlabeled',
                'video_type': 'test'
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['video']['title'], 'test_fallback_name')
        
        # Verify the model has the correct title
        video_id = data['video_id']
        video = Video.objects.get(id=video_id)
        self.assertEqual(video.title, 'test_fallback_name')
        
        # Clean up files created during test
        _delete_video_files(video)
        video.delete()

        # Test case 2: Upload with missing title parameter
        video_file2 = SimpleUploadedFile("test_fallback_missing.mp4", b"dummy_content", content_type="video/mp4")
        response2 = self.client.post(
            reverse('ajax_upload_video'),
            {
                'video_file': video_file2,
                'label': 'unlabeled',
                'video_type': 'test'
            }
        )
        self.assertEqual(response2.status_code, 200)
        data2 = response2.json()
        self.assertEqual(data2['status'], 'success')
        self.assertEqual(data2['video']['title'], 'test_fallback_missing')
        
        # Verify and clean up
        video_id2 = data2['video_id']
        video2 = Video.objects.get(id=video_id2)
        self.assertEqual(video2.title, 'test_fallback_missing')
        _delete_video_files(video2)
        video2.delete()
