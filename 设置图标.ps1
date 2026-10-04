# ==========================================================
#  给 Qiuli 套上「QL」图标
#
#  背景：Windows 不允许 .bat 文件自带图标，所以做法是
#        建两个带图标的快捷方式（Qiuli / Qiuli 管理员）。
#
#  运行方式：右键本文件 → 「使用 PowerShell 运行」
#  或者在本目录执行：
#      powershell -ExecutionPolicy Bypass -File .\设置图标.ps1
#
#  加 -QlAssoc 参数可以顺便让所有 .ql 文件也显示这个图标：
#      powershell -ExecutionPolicy Bypass -File .\设置图标.ps1 -QlAssoc
# ==========================================================

param(
    [switch]$QlAssoc
)

$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ico = Join-Path $dir "qiuli.ico"

function Say($text, $color = "Gray") {
    Write-Host $text -ForegroundColor $color
}

Say ""
Say "  Qiuli 图标设置" "Cyan"
Say "  ────────────────────────────────" "DarkGray"

if (-not (Test-Path $ico)) {
    Say "  找不到图标文件：qiuli.ico" "Red"
    Say "  请先生成图标：python tools\make_icon.py" "Yellow"
    exit 1
}

# ---------- 1. 创建快捷方式 ----------
try {
    $ws = New-Object -ComObject WScript.Shell

    $pairs = @(
        @{ Lnk = "Qiuli.lnk";          Target = "qiuli.bat";     Desc = "Qiuli 语言交互环境（REPL）" },
        @{ Lnk = "Qiuli 管理员.lnk";    Target = "管理员通道.bat"; Desc = "Qiuli 管理员通道" }
    )

    foreach ($p in $pairs) {
        $lnkPath = Join-Path $dir $p.Lnk
        $target = Join-Path $dir $p.Target
        if (-not (Test-Path $target)) {
            Say ("  跳过 {0}（找不到 {1}）" -f $p.Lnk, $p.Target) "Yellow"
            continue
        }
        $s = $ws.CreateShortcut($lnkPath)
        $s.TargetPath = $target
        $s.WorkingDirectory = $dir
        $s.IconLocation = "$ico,0"
        $s.Description = $p.Desc
        $s.Save()
        Say ("  ✔ 已创建 {0}" -f $p.Lnk) "Green"
    }
} catch {
    Say ("  创建快捷方式失败：" + $_.Exception.Message) "Red"
}

# ---------- 2. 可选：.ql 文件图标关联 ----------
if ($QlAssoc) {
    try {
        $progId = "Qiuli.Script"
        $classes = "HKCU:\Software\Classes"

        New-Item -Path "$classes\.ql" -Force | Out-Null
        Set-ItemProperty -Path "$classes\.ql" -Name "(default)" -Value $progId

        New-Item -Path "$classes\$progId" -Force | Out-Null
        Set-ItemProperty -Path "$classes\$progId" -Name "(default)" -Value "Qiuli 脚本"

        New-Item -Path "$classes\$progId\DefaultIcon" -Force | Out-Null
        Set-ItemProperty -Path "$classes\$progId\DefaultIcon" -Name "(default)" -Value "$ico,0"

        # 双击用 qiuli.py 运行
        $cli = Join-Path $dir "qiuli.py"
        $py = (Get-Command python -ErrorAction SilentlyContinue).Source
        if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
        if ($py) {
            New-Item -Path "$classes\$progId\shell\open\command" -Force | Out-Null
            Set-ItemProperty -Path "$classes\$progId\shell\open\command" -Name "(default)" `
                -Value "`"$py`" `"$cli`" `"%1`""
            Say "  ✔ 已关联 .ql（双击即可运行）" "Green"
        } else {
            Say "  ! 没找到 python，.ql 只设置了图标，未设置打开方式" "Yellow"
        }
        Say "  ✔ 已把 .ql 文件图标换成 QL" "Green"
    } catch {
        Say ("  设置 .ql 关联失败：" + $_.Exception.Message) "Red"
    }
}

# ---------- 3. 刷新图标缓存 ----------
try {
    $sig = '[DllImport("shell32.dll")] public static extern void SHChangeNotify(int e, int f, IntPtr a, IntPtr b);'
    Add-Type -MemberDefinition $sig -Name Shell32 -Namespace Win32 | Out-Null
    [Win32.Shell32]::SHChangeNotify(0x08000000, 0x1000, [IntPtr]::Zero, [IntPtr]::Zero)
    Say "  ✔ 已刷新图标缓存" "Green"
} catch {
    # 刷新失败不影响使用，重启资源管理器即可
}

Say ""
Say "  完成！桌面/文件夹里现在有两个带 QL 图标的入口：" "Cyan"
Say "      Qiuli.lnk          → 双击进入交互环境（REPL）" "Gray"
Say "      Qiuli 管理员.lnk    → 双击进入管理员通道" "Gray"
Say ""
Say "  提示：如果图标还是旧的，注销一次或重启资源管理器即可。" "DarkGray"
Say ""
if (-not $QlAssoc) {
    Say "  想让 .ql 文件也用这个图标？加参数再跑一次：" "DarkGray"
    Say "      powershell -ExecutionPolicy Bypass -File .\设置图标.ps1 -QlAssoc" "DarkGray"
    Say ""
}
Read-Host "按回车关闭"
