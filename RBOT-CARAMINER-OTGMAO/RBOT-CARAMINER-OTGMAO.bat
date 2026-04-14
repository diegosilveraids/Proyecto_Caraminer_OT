:: Original (machine-specific, kept for reference)
:: cd C:\Users\Juan Pacheco\Downloads\rocketbot_win_20251015\Rocketbot
:: rocketbot.exe -start=RBOT-CARAMINER-OTGMAO -db="C:/Users/Juan Pacheco/Documents/GitHub/CARAMINER-OTGMAO\RBOT-CARAMINER-OTGMAO\robot.db"

@echo off
if "%ROCKETBOT_HOME%"=="" (
    echo Error: ROCKETBOT_HOME is not set.
    echo Set it to your Rocketbot installation folder, e.g.:
    echo   setx ROCKETBOT_HOME "C:\path\to\Rocketbot"
    exit /b 1
)
"%ROCKETBOT_HOME%\rocketbot.exe" -start=RBOT-CARAMINER-OTGMAO -db="%~dp0robot.db"