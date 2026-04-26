# Generated migration for adding video_type field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('detector', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='video',
            name='video_type',
            field=models.CharField(
                choices=[('sample', 'Sample (for training)'), ('test', 'Test (for detection)')],
                default='sample',
                max_length=20
            ),
        ),
    ]
