@echo off
chcp 65001 >nul 2>&1
title 大学生系统 - 一键迁移
echo ==========================================
echo   大学生学习与求职智能助手 - 一键迁移
echo ==========================================
echo.
echo 本脚本将自动完成：
echo   1. 检查 Docker / Python / Node.js 环境
echo   2. 启动 Docker 容器 (MySQL + Redis + Chroma)
echo   3. 创建 Python 虚拟环境 + 安装依赖
echo   4. 配置 .env 文件
echo   5. 初始化数据库表结构
echo   6. (可选) 爬取小林面试笔记入库
echo   7. 安装前端依赖
echo   8. 启动后端 + 前端 + 打开浏览器
echo.
echo 首次在新电脑部署时使用，已配好的电脑用"一键启动.bat"即可。
echo.
pause

powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0迁移脚本.ps1"

echo.
echo 脚本执行完毕，按任意键关闭窗口...
pause >nul
