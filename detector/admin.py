from django.contrib import admin
from .models import Video, AnalysisResult, ForgeryRegion, TrainingSession

admin.site.register(Video)
admin.site.register(AnalysisResult)
admin.site.register(ForgeryRegion)
admin.site.register(TrainingSession)
