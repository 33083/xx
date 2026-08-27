@echo off
setlocal enabledelayedexpansion
title 大学生学习与求职智能助手 - 一键启动
echo ==========================================
echo   大学生学习与求职智能助手 - 一键启动
echo ==========================================
echo.

cd /d "%~dp0"

rem ---------- 0. 数据层 (Docker: MySQL 3306) ----------
netstat -ano | findstr ":3306 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo [数据层] MySQL 3306 已在运行，跳过
  goto :mysql_ready
)

echo [数据层] MySQL 未运行，尝试通过 Docker 启动数据服务...
docker info >nul 2>&1
if errorlevel 1 (
  echo [数据层] Docker 未运行，正在自动启动 Docker Desktop，请稍候...
  if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
  ) else if exist "%LocalAppData%\Docker\Docker Desktop.exe" (
    start "" "%LocalAppData%\Docker\Docker Desktop.exe"
  ) else (
    echo [数据层] 未找到 Docker Desktop，请手动启动后重新运行本脚本
    pause
    exit /b 1
  )
  set /a dk=0
  :wait_docker
  timeout /t 5 /nobreak >nul
  docker info >nul 2>&1
  if not errorlevel 1 goto docker_ready
  set /a dk+=1
  if !dk! LSS 36 goto wait_docker
  echo [数据层] Docker Desktop 启动超时，请手动打开后重新运行
  pause
  exit /b 1
  :docker_ready
  echo [数据层] Docker 引擎已就绪
)

docker compose up -d
echo [数据层] 等待 MySQL 就绪...
set /a cnt=0
:wait_mysql
netstat -ano | findstr ":3306 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo [数据层] MySQL 已就绪
  goto :mysql_ready
)
set /a cnt+=1
if !cnt! LSS 30 (
  timeout /t 2 /nobreak >nul
  goto wait_mysql
)
echo [数据层] MySQL 启动超时，请检查 Docker 状态
pause
exit /b 1

:mysql_ready
rem ---------- 1. 后端 (FastAPI, 端口 8000) ----------
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo [后端] 端口 8000 已在运行，跳过启动
  goto :backend_ready
)
echo [后端] 正在启动... 请在新窗口查看日志
cd /d "%~dp0backend"
start "大学生系统-后端-8000" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
cd /d "%~dp0"
:backend_ready

rem ---------- 2. 前端 (Vue+Vite, 端口 5173) ----------
netstat -ano | findstr ":5173 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo [前端] 端口 5173 已在运行，跳过启动
  goto :frontend_ready
)
echo [前端] 正在启动... 请在新窗口查看日志
cd /d "%~dp0frontend"
start "大学生系统-前端-5173" cmd /k "npm run dev"
cd /d "%~dp0"
:frontend_ready

echo.
echo 等待服务启动中，请稍候...
timeout /t 8 /nobreak >nul

echo 正在打开浏览器: http://localhost:5173
start "" http://localhost:5173

echo.
echo ==========================================
echo   启动完成！
echo   网页: http://localhost:5173
echo   后端接口: http://localhost:8000/docs
echo   说明: 关闭弹出的两个服务窗口即停止服务
echo ==========================================
pause
