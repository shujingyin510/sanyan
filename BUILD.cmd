@echo off
chcp 65001 >nul
title 三言 — 构建安装包

echo ========================================
echo  三言 v3.12.0 — 构建安装包
echo ========================================
echo.

echo [1/3] 清理历史构建...
rmdir /s /q dist build 2>nul
del *.spec 2>nul
echo 完成.

echo [2/3] 构建 exe...
python -X utf8 build_exe.py
if %errorlevel% neq 0 (
    echo 构建 exe 失败!
    pause
    exit /b 1
)

echo [3/3] 构建安装程序 (Inno Setup)...
rem 请先安装 Inno Setup: https://jrsoftware.org/isdl.php
iscc installer.iss
if %errorlevel% equ 0 (
    echo.
    echo ✓ 安装包已生成: dist\三言-3.12.0-安装程序.exe
) else (
    echo.
    echo 提示: 请先安装 Inno Setup (https://jrsoftware.org/isdl.php)
    echo 安装后确保 iscc.exe 在 PATH 中。
    echo exe 已生成于: dist\三言.exe
)

echo.
pause
