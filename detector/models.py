"""
Database models for Video Forgery Detection System.
"""
import os
from django.db import models
from django.conf import settings


class Video(models.Model):
    """Stores uploaded video metadata."""
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('processing', 'Processing'),
        ('analyzed', 'Analyzed'),
        ('error', 'Error'),
    ]
    LABEL_CHOICES = [
        ('unlabeled', 'Unlabeled'),
        ('real', 'Real'),
        ('fake', 'Fake'),
    ]
    VIDEO_TYPE_CHOICES = [
        ('sample', 'Sample (for training)'),
        ('test', 'Test (for detection)'),
    ]

    title = models.CharField(max_length=255)
    video_file = models.FileField(upload_to='inputvideos/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    label = models.CharField(max_length=20, choices=LABEL_CHOICES, default='unlabeled')
    video_type = models.CharField(max_length=20, choices=VIDEO_TYPE_CHOICES, default='sample')
    frame_count = models.IntegerField(default=0)
    duration_seconds = models.FloatField(default=0.0)
    file_size_mb = models.FloatField(default=0.0)
    thumbnail = models.ImageField(upload_to='thumbnails/', null=True, blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def frames_dir(self):
        """Directory where extracted frames are stored, categorized by label."""
        label_dir = self.label if self.label != 'unlabeled' else 'training'
        return os.path.join(settings.MEDIA_ROOT, 'frames', label_dir, str(self.id))

    @property
    def video_path(self):
        """Full path to the video file."""
        return os.path.join(settings.MEDIA_ROOT, str(self.video_file))


class AnalysisResult(models.Model):
    """Stores detection results for a video."""
    VERDICT_CHOICES = [
        ('real', 'Real / Authentic'),
        ('fake', 'Fake / Forged'),
    ]

    video = models.OneToOneField(Video, on_delete=models.CASCADE, related_name='result')
    verdict = models.CharField(max_length=10, choices=VERDICT_CHOICES)
    confidence = models.FloatField(default=0.0)
    total_frames_analyzed = models.IntegerField(default=0)
    fake_frame_count = models.IntegerField(default=0)
    real_frame_count = models.IntegerField(default=0)
    frame_predictions = models.JSONField(default=list)
    analyzed_at = models.DateTimeField(auto_now_add=True)
    processing_time_seconds = models.FloatField(default=0.0)
    screenshot = models.ImageField(upload_to='screenshots/', null=True, blank=True)

    def __str__(self):
        return f"{self.video.title} → {self.get_verdict_display()} ({self.confidence:.1%})"

    @property
    def fake_percentage(self):
        if self.total_frames_analyzed == 0:
            return 0
        return (self.fake_frame_count / self.total_frames_analyzed) * 100

    @property
    def results_dir(self):
        """Directory where result images are stored."""
        return os.path.join(settings.MEDIA_ROOT, 'results', str(self.video.id))


class ForgeryRegion(models.Model):
    """Stores detected forged regions in individual frames."""
    result = models.ForeignKey(AnalysisResult, on_delete=models.CASCADE, related_name='regions')
    frame_number = models.IntegerField()
    original_frame = models.ImageField(upload_to='results/originals/')
    annotated_frame = models.ImageField(upload_to='results/annotated/')
    region_description = models.CharField(max_length=255, default='Suspicious Region')
    confidence = models.FloatField(default=0.0)
    bbox_x = models.IntegerField(default=0)
    bbox_y = models.IntegerField(default=0)
    bbox_width = models.IntegerField(default=0)
    bbox_height = models.IntegerField(default=0)

    class Meta:
        ordering = ['frame_number']

    def __str__(self):
        return f"Frame {self.frame_number}: {self.region_description} ({self.confidence:.1%})"


class TrainingSession(models.Model):
    """Tracks model training runs."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('training', 'Training'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    epochs = models.IntegerField(default=50)
    batch_size = models.IntegerField(default=16)
    total_videos = models.IntegerField(default=0)
    total_frames = models.IntegerField(default=0)
    final_accuracy = models.FloatField(null=True, blank=True)
    final_loss = models.FloatField(null=True, blank=True)
    val_accuracy = models.FloatField(null=True, blank=True)
    val_loss = models.FloatField(null=True, blank=True)
    model_path = models.CharField(max_length=500, blank=True)
    training_log = models.JSONField(default=list)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Training {self.id} - {self.get_status_display()} ({self.started_at})"
