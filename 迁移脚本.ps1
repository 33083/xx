#Requires -Version 5.1
<#
.SYNOPSIS
  大学生学习与求职智能助手 · 一键迁移脚本
  在新电脑上从零配置：检查环境 → 自动安装缺失工具 → 装依赖 → 启动 Docker → 初始化数据库 → 启动服务
.AUTHOR
  自动生成
.USAGE
  右键以管理员身份运行"一键迁移.bat"，或在本目录执行：
  powershell -ExecutionPolicy Bypass -File "迁移脚本.ps1"
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Write-Step  { param([string]$msg) Write-Host "`n[STEP] $msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn  { param([string]$msg) Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Err   { param([string]$msg) Write-Host "  [ERR] $msg" -ForegroundColor Red }
function Write-Info  { param([string]$msg) Write-Host "  $msg" -ForegroundColor Gray }

function Test-Command { param([string]$cmd) return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Test-Port    { param([int]$p) return [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) }

function Wait-Port {
    param([int]$Port, [int]$TimeoutSec = 120, [string]$Label = "")
    $lbl = if ($Label) { $Label } else { "端口 $Port" }
    $elapsed = 0
    while ($elapsed -lt $TimeoutSec) {
        if (Test-Port $Port) { Write-Ok "$lbl 已就绪 (port $Port)"; return $true }
        Start-Sleep -Seconds 2; $elapsed += 2
        if ($elapsed % 10 -eq 0) { Write-Info "等待 $lbl... ${elapsed}s" }
    }
    Write-Err "$lbl 等待超时 (${TimeoutSec}s)"
    return $false
}

# 刷新当前会话 PATH（winget 装完后当前进程的 PATH 不会自动更新）
function Refresh-Path {
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"
}

# ============================================================
Write-Host "==========================================" -ForegroundColor White
Write-Host "  一键迁移脚本 · 大学生学习与求职智能助手" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor White

# ============================================================
# 1. 环境检查 + 自动安装（winget）
# ============================================================
Write-Step "1/7 环境检查 + 自动安装"

# --- 检查 winget 是否可用 ---
$hasWinget = Test-Command "winget"
if ($hasWinget) {
    Write-Ok "winget 可用，支持自动安装缺失工具"
} else {
    Write-Warn "winget 不可用（Windows 版本过低或精简版系统）"
    Write-Warn "将退回手动模式：打印下载链接让你手动装"
}

# --- winget 包 ID 映射 ---
$pkgs = @{
    "docker" = @{ Id = "Docker.DockerDesktop"; Name = "Docker Desktop"; Url = "https://www.docker.com/products/docker-desktop/" }
    "python" = @{ Id = "Python.Python.3.12";   Name = "Python 3.12";    Url = "https://www.python.org/downloads/" }
    "node"   = @{ Id = "OpenJS.NodeJS.LTS";    Name = "Node.js LTS";    Url = "https://nodejs.org/" }
}

$needRestart = $false

# --- 逐个检查 + 自动安装 ---
foreach ($cmd in @("docker", "python", "node")) {
    $pkg = $pkgs[$cmd]

    if (Test-Command $cmd) {
        $ver = & $cmd --version 2>&1
        Write-Ok "$($pkg.Name) 已安装: $ver"
        continue
    }

    # 没装，尝试 winget 自动安装
    if ($hasWinget) {
        Write-Info "$($pkg.Name) 未安装，开始通过 winget 自动安装..."
        Write-Info "  winget install $($pkg.Id) --silent"
        winget install $pkg.Id --silent --accept-package-agreements --accept-source-agreements --disable-interactivity 2>&1 |
            ForEach-Object { Write-Info "  $_" }

        if ($LASTEXITCODE -eq 0) {
            Write-Ok "$($pkg.Name) 安装命令已完成"
            Refresh-Path
            # 再检查一次
            if (Test-Command $cmd) {
                $ver = & $cmd --version 2>&1
                Write-Ok "$($pkg.Name) 验证成功: $ver"
            } else {
                Write-Warn "$($pkg.Name) 已安装但当前会话未生效（PATH 未刷新）"
                Write-Warn "后续步骤可能报错，重启电脑后再跑一次本脚本即可"
                $needRestart = $true
            }
            # Docker 和 Python 装完通常需要重启才能完全生效
            if ($cmd -in @("docker", "python")) {
                $needRestart = $true
            }
        } else {
            Write-Warn "$($pkg.Name) winget 安装失败（exit $LASTEXITCODE）"
            Write-Warn "请手动安装: $($pkg.Url)"
            $needRestart = $true
        }
    } else {
        # winget 不可用，打印链接让用户手动装
        Write-Err "$($pkg.Name) 未安装，请手动下载安装:"
        Write-Host "    $($pkg.Url)" -ForegroundColor Yellow
        $needRestart = $true
    }
}

# npm 随 Node.js 一起装，单独检查
if (Test-Command "npm") {
    $npmVer = (npm --version 2>&1)
    Write-Ok "npm 已安装: $npmVer"
} else {
    if (Test-Command "node") {
        Write-Warn "Node.js 已装但 npm 未找到，刷新 PATH 后重试..."
        Refresh-Path
        if (Test-Command "npm") {
            Write-Ok "npm 刷新后可用"
        } else {
            Write-Warn "npm 仍未找到，请重启电脑后再试"
            $needRestart = $true
        }
    } else {
        Write-Warn "npm 随 Node.js 一起安装，上面已处理 Node.js"
    }
}

# --- 如果装了 Docker/Python/Node，提示重启 ---
if ($needRestart) {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Yellow
    Write-Host "  刚刚安装了 Docker / Python / Node.js" -ForegroundColor Yellow
    Write-Host "  这些软件需要重启电脑后 PATH 才能完全生效" -ForegroundColor Yellow
    Write-Host "==========================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  脚本现在退出，重启后不用从头开始：" -ForegroundColor Gray
    Write-Host "  已装好的工具会自动跳过，直接继续后续步骤" -ForegroundColor Gray
    Write-Host ""
    $choice = Read-Host "是否现在重启电脑？重启后再双击'一键迁移.bat'继续 [y/N]"
    if ($choice -tolower() -eq "y") {
        Write-Info "10 秒后重启电脑..."
        Start-Sleep -Seconds 10
        Restart-Computer -Force
    } else {
        Write-Host "请手动重启电脑后再双击'一键迁移.bat'继续" -ForegroundColor Yellow
    }
    exit 0
}

# ============================================================
# 2. Docker 服务启动（MySQL + Redis + Chroma）
# ============================================================
Write-Step "2/7 启动 Docker 容器（MySQL + Redis + Chroma）"

# 检查 Docker 是否在运行
$dockerOk = $false
try { docker info *> $null; $dockerOk = $true } catch {}

if (-not $dockerOk) {
    Write-Info "Docker Desktop 未运行，尝试自动启动..."
    $ddPaths = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "$env:LocalAppData\Docker\Docker\Docker Desktop.exe"
    )
    $started = $false
    foreach ($p in $ddPaths) {
        if (Test-Path $p) { Start-Process $p; $started = $true; break }
    }
    if (-not $started) {
        Write-Err "未找到 Docker Desktop，请手动启动后重跑本脚本"
        exit 1
    }
    Write-Info "等待 Docker Desktop 启动..."
    $dkWait = 0
    while ($dkWait -lt 120) {
        try { docker info *> $null; break } catch {}
        Start-Sleep -Seconds 3; $dkWait += 3
        if ($dkWait % 15 -eq 0) { Write-Info "  Docker 启动中... ${dkWait}s" }
    }
    if ($dkWait -ge 120) { Write-Err "Docker Desktop 启动超时"; exit 1 }
    Write-Ok "Docker Desktop 已就绪"
}

# 启动容器
Write-Info "执行 docker compose up -d..."
docker compose up -d
if ($LASTEXITCODE -ne 0) { Write-Err "docker compose 启动失败"; exit 1 }
Write-Ok "容器已启动"

# 等待三个服务就绪
Write-Info "等待 MySQL 就绪 (3306)..."
if (-not (Wait-Port -Port 3306 -TimeoutSec 60 -Label "MySQL")) { exit 1 }

Write-Info "等待 Redis 就绪 (6379)..."
if (-not (Wait-Port -Port 6379 -TimeoutSec 30 -Label "Redis")) { Write-Warn "Redis 未就绪，限流功能将降级为内存模式" }

Write-Info "等待 Chroma 就绪 (8001)..."
if (-not (Wait-Port -Port 8001 -TimeoutSec 60 -Label "Chroma")) { Write-Warn "Chroma 未就绪，RAG 功能不可用" }

# 额外等一下 MySQL 完全接受连接
Start-Sleep -Seconds 3
Write-Ok "Docker 服务全部就绪"

# ============================================================
# 3. Python 虚拟环境 + 依赖安装
# ============================================================
Write-Step "3/7 配置 Python 后端环境"

$venvPath = Join-Path $ProjectRoot "backend\.venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$venvPip = Join-Path $venvPath "Scripts\pip.exe"

if (-not (Test-Path $venvPython)) {
    Write-Info "创建虚拟环境 (.venv)..."
    Push-Location "$ProjectRoot\backend"
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Err "venv 创建失败"; Pop-Location; exit 1 }
    Pop-Location
    Write-Ok "虚拟环境已创建"
} else {
    Write-Ok "虚拟环境已存在，跳过创建"
}

# 安装依赖
Write-Info "安装 Python 依赖 (requirements.txt)..."
Push-Location "$ProjectRoot\backend"
& $venvPip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Warn "静默安装失败，尝试详细模式..."
    & $venvPip install -r requirements.txt
}
Pop-Location
Write-Ok "Python 依赖安装完成"

# ============================================================
# 4. .env 配置文件
# ============================================================
Write-Step "4/7 检查 .env 配置文件"

$envFile = Join-Path $ProjectRoot "backend\.env"
$envExample = Join-Path $ProjectRoot "backend\.env.example"

if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-Ok "已从 .env.example 创建 .env"
    } else {
        Write-Err "backend\.env 和 .env.example 都不存在，请手动创建 .env"
        exit 1
    }
} else {
    Write-Ok ".env 已存在"
}

# 检查 DEEPSEEK_API_KEY 是否填写
$envContent = Get-Content $envFile -Raw
if ($envContent -match "DEEPSEEK_API_KEY\s*=\s*(\S+)") {
    $keyVal = $matches[1]
    if ($keyVal -ne "" -and $keyVal -ne "your_key_here" -and $keyVal -ne "sk-xxx") {
        Write-Ok "DEEPSEEK_API_KEY 已配置"
    } else {
        Write-Warn "DEEPSEEK_API_KEY 未填写，聊天功能将不可用！"
        Write-Warn "请编辑 backend\.env 填入你的 DeepSeek API Key"
        Write-Warn "注册地址: https://platform.deepseek.com/"
    }
} else {
    Write-Warn "未找到 DEEPSEEK_API_KEY 配置项"
}

# ============================================================
# 5. 数据库初始化（建表 + 公共题库入库）
# ============================================================
Write-Step "5/7 数据库初始化"

# FastAPI 启动时 Base.metadata.create_all 会自动建表
# 但我们先手动跑一次确保表结构存在
Write-Info "创建数据库表结构..."
$initScript = @"
import sys
sys.path.insert(0, r'$ProjectRoot\backend')
from app.core.database import engine, Base
from app.models import user, conversation, document, skill
Base.metadata.create_all(bind=engine)
print('表结构创建完成')
"@
$initScript | & $venvPython - 2>&1 | ForEach-Object { Write-Info "  $_" }
Write-Ok "数据库表结构就绪"

# 公共题库入库（可选）
$seedScript = Join-Path $ProjectRoot "backend\scripts\seed_xiaolinnote.py"
$seedScriptAlt = Join-Path $ProjectRoot "seed_xiaolinnote.py"
$seedFound = $false
$seedPath = ""
if (Test-Path $seedScript) { $seedPath = $seedScript; $seedFound = $true }
elseif (Test-Path $seedScriptAlt) { $seedPath = $seedScriptAlt; $seedFound = $true }

if ($seedFound) {
    Write-Info "找到公共面试题库爬取脚本: $seedPath"
    $choice = Read-Host "是否现在爬取并入库小林面试笔记 (86篇，约2分钟)? [Y/n]"
    if ($choice -eq "" -or $choice -tolower() -eq "y") {
        Write-Info "开始爬取入库..."
        & $venvPython $seedPath 2>&1 | ForEach-Object {
            if ($_ -match "\[OK\]") { Write-Ok $_ }
            elseif ($_ -match "\[WARN\]|\[ERR\]") { Write-Warn $_ }
            else { Write-Info $_ }
        }
        Write-Ok "公共题库入库完成"
    } else {
        Write-Info "跳过题库入库（后续可手动运行: python $seedPath）"
    }
} else {
    Write-Warn "未找到 seed_xiaolinnote.py，跳过公共题库入库"
}

# ============================================================
# 6. 前端依赖安装
# ============================================================
Write-Step "6/7 配置前端环境"

$nodeModules = Join-Path $ProjectRoot "frontend\node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Info "安装前端依赖 (npm install)..."
    Push-Location "$ProjectRoot\frontend"
    npm install --silent 2>&1 | ForEach-Object { Write-Info "  $_" }
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "静默安装失败，尝试详细模式..."
        npm install
    }
    Pop-Location
    Write-Ok "前端依赖安装完成"
} else {
    Write-Ok "node_modules 已存在，跳过安装"
}

# ============================================================
# 7. 启动服务
# ============================================================
Write-Step "7/7 启动后端 + 前端"

# 后端
if (Test-Port 8000) {
    Write-Ok "后端已在运行 (port 8000)"
} else {
    Write-Info "启动后端 (FastAPI :8000)..."
    $backendCmd = "cd /d `"$ProjectRoot\backend`" && `"$venvPython`" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    Start-Process cmd -ArgumentList "/k", "title 大学生系统-后端-8000 && $backendCmd" -WindowStyle Normal
    if (-not (Wait-Port -Port 8000 -TimeoutSec 30 -Label "后端")) {
        Write-Warn "后端启动较慢，请查看新窗口日志"
    }
}

# 前端
if (Test-Port 5173) {
    Write-Ok "前端已在运行 (port 5173)"
} else {
    Write-Info "启动前端 (Vite :5173)..."
    $frontendCmd = "cd /d `"$ProjectRoot\frontend`" && npm run dev"
    Start-Process cmd -ArgumentList "/k", "title 大学生系统-前端-5173 && $frontendCmd" -WindowStyle Normal
    if (-not (Wait-Port -Port 5173 -TimeoutSec 30 -Label "前端")) {
        Write-Warn "前端启动较慢，请查看新窗口日志"
    }
}

# 打开浏览器
Start-Sleep -Seconds 3
Write-Info "打开浏览器..."
Start-Process "http://localhost:5173"

# ============================================================
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  迁移完成！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  前端页面:  http://localhost:5173" -ForegroundColor White
Write-Host "  后端接口:  http://localhost:8000/docs" -ForegroundColor White
Write-Host "  API 文档:  http://localhost:8000/redoc" -ForegroundColor White
Write-Host ""
Write-Host "  首次使用请先注册账号" -ForegroundColor Yellow
Write-Host "  如果 DEEPSEEK_API_KEY 未配置，请编辑 backend\.env" -ForegroundColor Yellow
Write-Host "  关闭服务：直接关闭后端/前端两个命令行窗口" -ForegroundColor Gray
Write-Host "  重新启动：双击 一键启动.bat（跳过环境配置）" -ForegroundColor Gray
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
