@echo off
echo ========================================
echo  Encheres Sellees - Demarrage
echo ========================================
echo.

echo [1/2] Demarrage du backend API (port 8000)...
start "Backend API" cmd /k "cd /d "%~dp0" && python -m uvicorn backend_api.main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak > nul

echo [2/2] Demarrage du frontend (port 5173)...
start "Frontend" cmd /k "cd /d "%~dp0\frontend" && npm run dev"

echo.
echo Backend : http://localhost:8000
echo Frontend : http://localhost:5173
echo.
echo Fermez les fenetres pour arreter les serveurs.
pause
