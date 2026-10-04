"""Qiuli 测试套件

运行方式：
    python qiuli.py test
    python tests/run_tests.py [过滤词]

会做两件事：
  1. 执行 tests/cases/*.ql —— 每个用例靠 断言 自检，退出码非 0 即失败
  2. 对 examples/ 与 stdlib/ 下的所有 .ql 做语法检查
"""

import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PY = sys.executable
CLI = os.path.join(ROOT, "qiuli.py")

GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"


def c(text, code):
    if os.environ.get("NO_COLOR"):
        return text
    return "%s%s%s" % (code, text, RESET)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=ROOT, **kw)


def collect(d):
    base = os.path.join(ROOT, d)
    if not os.path.isdir(base):
        return []
    out = []
    for name in sorted(os.listdir(base)):
        if name.endswith(".ql"):
            out.append(os.path.join(d, name))
    return out


def main(argv=None):
    argv = list(argv or [])
    filt = argv[0] if argv else None
    started = time.perf_counter()

    print(c("\n  Qiuli 测试套件", BOLD))
    print(c("  " + "─" * 46, DIM))

    # ---------- 1. 用例 ----------
    cases = collect("tests/cases")
    if filt:
        cases = [p for p in cases if filt in p]
    passed, failed = [], []
    for path in cases:
        r = run([PY, CLI, "run", path])
        ok = (r.returncode == 0) and ("✔" in r.stdout or "通过" in r.stdout)
        if ok:
            passed.append(path)
            print("  %s %s" % (c("✔", GREEN), os.path.basename(path)))
        else:
            failed.append(path)
            print("  %s %s" % (c("✘", RED), os.path.basename(path)))
            tail = (r.stdout or "").strip().split("\n")[-6:]
            for line in tail:
                print("      %s" % c(line, DIM))
            if r.stderr.strip():
                print("      %s" % c(r.stderr.strip().split("\n")[-1], RED))

    # ---------- 2. 语法检查 ----------
    print(c("\n  语法检查", BOLD))
    print(c("  " + "─" * 46, DIM))
    others = collect("examples") + collect("stdlib")
    syn_ok, syn_bad = 0, []
    for path in others:
        r = run([PY, CLI, "check", path])
        if r.returncode == 0:
            syn_ok += 1
        else:
            syn_bad.append(path)
            print("  %s %s" % (c("✘", RED), path))
            print("      %s" % c((r.stdout or r.stderr).strip().split("\n")[-1], RED))
    print("  %s %d 个文件语法正确" % (c("✔", GREEN), syn_ok))

    # ---------- 3. 命令行冒烟测试 ----------
    print(c("\n  命令行冒烟测试", BOLD))
    print(c("  " + "─" * 46, DIM))
    cli_checks = [
        (["version"], "Qiuli", "版本信息"),
        (["--help"], "用法", "帮助文本"),
        (["admin", "命令"], "内置命令", "管理员命令列表"),
        (["check", "examples/01_你好世界.ql"], "语法检查通过", "语法检查"),
        (["tokens", "examples/模板.ql"], "KEYWORD", "词法输出"),
    ]
    cli_bad = []
    for argv, expect, label in cli_checks:
        r = run([PY, CLI] + argv)
        ok = r.returncode == 0 and (expect in (r.stdout or ""))
        if ok:
            print("  %s %s" % (c("✔", GREEN), label))
        else:
            cli_bad.append(label)
            print("  %s %s（期望输出包含 %r）" % (c("✘", RED), label, expect))
            print("      %s" % c((r.stdout or r.stderr).strip().split("\n")[-1], RED))

    # ---------- 4. Windows 脚本格式检查 ----------
    # .bat 必须是 CRLF（否则 cmd 会吃掉行首字符），含中文的要 GBK；
    # .ps1 必须带 UTF-8 BOM（否则 PowerShell 5.1 按 GBK 读，中文注释报错）
    print(c("\n  Windows 脚本格式检查", BOLD))
    print(c("  " + "─" * 46, DIM))
    fmt_bad = []
    fmt_checks = [
        (["qiuli.bat", "qiuli.cmd", "管理员通道.bat", "设置图标.bat"], "bat"),
        (["设置图标.ps1", "install.ps1"], "ps1"),
    ]
    for names, kind in fmt_checks:
        for name in names:
            p = os.path.join(ROOT, name)
            if not os.path.exists(p):
                continue
            raw = open(p, "rb").read()
            problems = []
            if kind == "bat":
                if b"\r\n" not in raw:
                    problems.append("行尾不是 CRLF（cmd 会吃掉行首字符）")
                try:
                    raw.decode("ascii")
                except UnicodeDecodeError:
                    try:
                        raw.decode("gbk")
                    except UnicodeDecodeError:
                        problems.append("编码既不是 ASCII 也不是 GBK")
            else:
                if not raw.startswith(b"\xef\xbb\xbf"):
                    problems.append("缺少 UTF-8 BOM（PowerShell 会按 GBK 读）")
            if problems:
                fmt_bad.append(name)
                print("  %s %-16s %s" % (c("✘", RED), name, "；".join(problems)))
            else:
                print("  %s %-16s 格式正确" % (c("✔", GREEN), name))

    # ---------- 汇总 ----------
    total = len(passed) + len(failed)
    dt = time.perf_counter() - started
    print("")
    print(c("  " + "═" * 46, DIM))
    if failed or syn_bad or cli_bad or fmt_bad:
        print("  %s 用例 %d/%d 通过，失败 %d；语法错误 %d；命令行异常 %d；格式问题 %d"
              % (c("✘ 测试未通过", RED), len(passed), total, len(failed),
                 len(syn_bad), len(cli_bad), len(fmt_bad)))
        for p in failed + cli_bad + fmt_bad:
            print("      %s %s" % (c("·", RED), p))
        return 1
    print("  %s 用例 %d/%d 全部通过，语法检查 %d 个文件，命令行 %d 项，"
          "格式检查 %d 个文件，耗时 %.2f 秒"
          % (c("✔ 全部通过", GREEN), len(passed), total, syn_ok,
             len(cli_checks), sum(len(n) for n, _ in fmt_checks), dt))
    print(c("  " + "═" * 46, DIM))
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
