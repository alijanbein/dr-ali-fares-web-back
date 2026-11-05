@echo off
cd /d "%~dp0"
pip install -r requirements.txt --quiet
echo Starting on http://localhost:8001
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8001
