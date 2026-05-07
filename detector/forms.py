"""
Forms for video upload and model training configuration.
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from .models import Video, UserProfile

User = get_user_model()


class UserRegistrationForm(UserCreationForm):
    """Enhanced registration form with additional user details."""
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last Name'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email Address'}))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Style all fields
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'premium-input'
            if field_name == 'password1':
                field.widget.attrs['placeholder'] = 'Create Password'
            elif field_name == 'password2':
                field.widget.attrs['placeholder'] = 'Confirm Password'


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = False

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


class ProfileForm(forms.ModelForm):
    """Update user profile details."""
    display_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Display name'})
    )
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Phone number'})
    )
    avatar = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-file-input', 'id': 'profile-avatar'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last name'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email address'}),
        }

    def __init__(self, *args, **kwargs):
        profile_instance = kwargs.pop('profile_instance', None)
        super(ProfileForm, self).__init__(*args, **kwargs)
        if profile_instance:
            self.fields['display_name'].initial = profile_instance.display_name
            self.fields['phone'].initial = profile_instance.phone
            self.fields['avatar'].initial = profile_instance.avatar

    def save(self, commit=True):
        user = super(ProfileForm, self).save(commit=commit)
        return user


class UserSettingsForm(forms.ModelForm):
    """User preferences and model settings."""
    preferred_frame_sample_rate = forms.IntegerField(
        min_value=1,
        max_value=30,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Frame sample rate',
        })
    )
    preferred_validation_split = forms.FloatField(
        min_value=0.05,
        max_value=0.5,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'step': '0.05',
            'placeholder': 'Validation split',
        })
    )
    detection_threshold = forms.FloatField(
        min_value=0.1,
        max_value=0.9,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'step': '0.05',
            'placeholder': 'Forgery threshold',
        })
    )
    show_heatmap = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'})
    )
    email_notifications = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'})
    )

    class Meta:
        model = UserProfile
        fields = [
            'preferred_frame_sample_rate',
            'preferred_validation_split',
            'detection_threshold',
            'show_heatmap',
            'email_notifications',
        ]


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
