
@echo off
echo Starting ForgeGuard AI (Video Forgery Detector)...
echo.
echo ========================================================
echo Setting up environment variables to bypass path limits
echo ========================================================
set PYTHONPATH=e:\tf_pkg;%PYTHONPATH%
set TF_ENABLE_ONEDNN_OPTS=0

echo Activating Virtual Environment...
call venv\Scripts\activate

echo Launching Django Server...
python manage.py runserver