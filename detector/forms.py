"""
Forms for video upload and model training configuration.
"""
from django import forms
from .models import Video


class VideoUploadForm(forms.ModelForm):
    """Form for uploading videos with label classification."""

    class Meta:
        model = Video
        fields = ['title', 'video_file', 'video_type', 'label']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter video title...',
                'id': 'video-title',
            }),
            'video_file': forms.ClearableFileInput(attrs={
                'class': 'form-file-input',
                'accept': 'video/*',
                'id': 'video-file',
            }),
            'video_type': forms.Select(attrs={
                'class': 'form-select',
                'id': 'video-type',
            }),
            'label': forms.Select(attrs={
                'class': 'form-select',
                'id': 'video-label',
            }),
        }

    def clean_video_file(self):
        video = self.cleaned_data.get('video_file')
        if video:
            # Validate file extension
            valid_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
            ext = '.' + video.name.split('.')[-1].lower()
            if ext not in valid_extensions:
                raise forms.ValidationError(
                    f'Unsupported video format. Supported: {", ".join(valid_extensions)}'
                )
        return video


class TrainingConfigForm(forms.Form):
    """Form for configuring model training parameters."""
    epochs = forms.IntegerField(
        initial=50, min_value=1, max_value=500,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'id': 'train-epochs',
        })
    )
    batch_size = forms.IntegerField(
        initial=16, min_value=1, max_value=128,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'id': 'train-batch-size',
        })
    )
    validation_split = forms.FloatField(
        initial=0.2, min_value=0.05, max_value=0.5,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'step': '0.05',
            'id': 'train-val-split',
        })
    )


class VideoDetectForm(forms.Form):
    """Form for selecting a video to run detection on."""
    video_id = forms.IntegerField(widget=forms.HiddenInput())
