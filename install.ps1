# ==========================================================
#  可选：把 Qiuli 加入用户 PATH
#  用法：powershell -ExecutionPolicy Bypass -File install.ps1
#  之后在新开的终端里可以直接敲： qiuli 你好.ql
# ==========================================================

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 创建一个 qiuli.cmd 包装，方便在任意目录调用
$cmd = @"
@echo off
chcp 65001 >nul
python "$dir\qiuli.py" %*
"@
Set-Content -Path (Join-Path $dir "qiuli.cmd") -Value $cmd -Encoding ASCII

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$dir*") {
    $newPath = if ($userPath) { "$userPath;$dir" } else { $dir }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host ""
    Write-Host "  已把 $dir 加入用户 PATH" -ForegroundColor Green
    Write-Host "  新开一个终端后即可使用： qiuli 你的脚本.ql" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  $dir 已经在 PATH 里了" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  试试看：" -ForegroundColor Cyan
Write-Host "    qiuli examples\01_你好世界.ql" -ForegroundColor Cyan
Write-Host "    qiuli              （进入 REPL）" -ForegroundColor Cyan
Write-Host ""
