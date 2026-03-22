@echo off
cd /d "D:\Claude\01_UFS\services\session-manager"
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
)
python -m app.main >> logs\service.log 2>&1
