@echo off
echo Building robots.db...
python build_db.py
if %errorlevel% neq 0 (
    echo Error building database.
    exit /b %errorlevel%
)
echo Done.