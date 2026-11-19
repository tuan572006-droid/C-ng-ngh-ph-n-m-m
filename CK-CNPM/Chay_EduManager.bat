@echo off
title Khoi dong He thong EduManager
cd /d "%~dp0"

echo [1/3] Dang khoi dong Backend (FastAPI)...
start "EduManager Backend" cmd /k "python -m uvicorn main:app --reload"

timeout /t 3 /nobreak >nul

echo [2/3] Dang khoi dong Giao dien (Streamlit)...
start "EduManager Frontend" cmd /k "python -m streamlit run app_ui.py --server.headless true"

timeout /t 3 /nobreak >nul

echo [3/3] Dang mo trinh duyet...
start http://localhost:8501

exit