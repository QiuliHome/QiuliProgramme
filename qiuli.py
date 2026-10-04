#!/usr/bin/env python3
"""Qiuli 语言命令行工具

用法：
    python qiuli.py                      进入交互式环境 REPL
    python qiuli.py 你好.ql              运行脚本
    python qiuli.py run 你好.ql          运行脚本
    python qiuli.py check 你好.ql        只做语法检查
    python qiuli.py ast 你好.ql          打印语法树
    python qiuli.py tokens 你好.ql       打印词法单元
    python qiuli.py test                 运行测试套件
    python qiuli.py new 脚本名           创建示例脚本
    python qiuli.py version              显示版本
"""

import os
import sys
import time

# 让 ql 源码目录可导入（无论从哪个工作目录启动）
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Windows 控制台：UTF-8 + 彩色
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if os.name == "nt":
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetConsoleMode(k.GetStdHandle(-11), 7)   # 启用 ANSI 转义
    except Exception:
        pass


def color(text, code, enabled=True):
    return "\033[%sm%s\033[0m" % (code, text) if enabled else text


HELP = """Qiuli（.ql）——一门为中文设计的脚本语言

用法：
    qiuli <文件.ql> [脚本参数...]      运行脚本
    qiuli run <文件.ql> [参数...]      运行脚本
    qiuli repl                         交互式环境（不带参数时默认进入）
    qiuli check <文件.ql>              语法检查（不执行）
    qiuli ast <文件.ql>                打印语法树（调试用）
    qiuli tokens <文件.ql>             打印词法单元（调试用）
    qiuli test                         运行 tests/ 下的测试
    qiuli new <名字>                   生成一个示例脚本
    qiuli 示例                         列出自带示例（可直接用名字运行）
    qiuli admin                        管理员通道（别名 / 注册命令 / 禁用 / 设置）
    qiuli version                      版本信息
    qiuli help                         本帮助

选项：
    --no-color      关闭彩色输出
    --time          显示运行耗时
"""


def find_script(name):
    """在项目目录里找脚本：examples/ 与 stdlib/（支持省略 .ql 后缀）"""
    cands = []
    for base in ("examples", "stdlib", ""):
        d = os.path.join(HERE, base) if base else HERE
        cands.append(os.path.join(d, name))
        cands.append(os.path.join(d, name + ".ql"))
    for c in cands:
        if os.path.exists(c) and os.path.isfile(c):
            return c
    # 模糊匹配：示例文件名以给定名字开头
    d = os.path.join(HERE, "examples")
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.endswith(".ql") and f.startswith(name):
                return os.path.join(d, f)
    return None


def run_registered(script, args, use_color=True, max_depth=800):
    """运行管理员注册到某个命令名下的 .ql 脚本"""
    if not os.path.exists(script):
        print(color("注册的脚本已经不在了：%s" % script, "31", use_color))
        print(color("（用 qiuli admin 注销 <名字> 可以删掉它）", "90", use_color))
        return 1
    from src.errors import QiuliError, QiuliRuntimeError
    from src.interpreter import Interpreter
    interp = Interpreter(base_dir=os.path.dirname(script) or os.getcwd(),
                         argv=list(args))
    interp.max_depth = max_depth
    try:
        interp.run_file(script, list(args))
    except QiuliError as e:
        print(e.render(use_color))
        return 1
    except QiuliRuntimeError as e:
        print(e.render(use_color))
        return 1
    except KeyboardInterrupt:
        print(color("\n（已中断）", "31", use_color))
        return 130
    except SystemExit as e:
        return int(e.code or 0)
    except Exception as e:
        if "--debug" in sys.argv:
            raise
        print(color("运行失败：%s: %s" % (type(e).__name__, e), "31", use_color))
        return 1
    return 0


def list_examples(use_color=True):
    """列出所有可用示例"""
    print(color("\n  Qiuli 自带示例（直接敲名字即可运行）\n", "93", use_color))
    for folder, title in (("examples", "示例"), ("stdlib", "标准库")):
        d = os.path.join(HERE, folder)
        if not os.path.isdir(d):
            continue
        files = sorted(f for f in os.listdir(d) if f.endswith(".ql"))
        print(color("  %s %s/" % ("▪", folder), "36", use_color))
        for f in files:
            print("      %-28s qiuli %s" % (f, f[:-3]))
        print()
    print(color("  也可以直接进入交互环境： qiuli", "90", use_color))
    print(color("  测试是否一切正常：     qiuli test\n", "90", use_color))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    use_color = "--no-color" not in argv
    if "--no-color" in argv:
        argv.remove("--no-color")
    show_time = "--time" in argv
    if "--time" in argv:
        argv.remove("--time")

    # ---- 管理员配置（别名 / 注册命令 / 禁用 / 设置项）----
    try:
        from src.admin import (load_config, resolve_alias, is_disabled,
                               get_script_command, get_setting, run_admin)
        cfg, _cfg_path = load_config()
    except Exception:
        cfg = None
        resolve_alias = lambda n, c=None: n          # noqa: E731
        is_disabled = lambda n, c=None: False        # noqa: E731
        get_script_command = lambda n, c=None: None  # noqa: E731
        get_setting = lambda k, c=None, d=None: d    # noqa: E731
        run_admin = None

    if cfg is not None:
        # 命令行上的 --no-color 优先级最高，其次是配置里的「彩色」
        if "--no-color" not in sys.argv and not get_setting("彩色", cfg, True):
            use_color = False

    if not argv:
        from src.repl import REPL
        from src.interpreter import Interpreter
        it = Interpreter(base_dir=os.getcwd())
        if cfg is not None:
            it.max_depth = int(get_setting("递归上限", cfg, 800) or 800)
        REPL(it, use_color).loop()
        return 0

    cmd = argv[0]
    rest = argv[1:]

    # 别名 → 真名
    cmd = resolve_alias(cmd, cfg)

    # 被管理员禁用了？
    if is_disabled(cmd, cfg):
        print(color("该命令已被管理员禁用：%s" % cmd, "31", use_color))
        print(color("（qiuli admin 启用 %s 可以恢复）" % cmd, "90", use_color))
        return 1

    # 注册的脚本命令：直接用解释器跑对应的 .ql
    info = get_script_command(cmd, cfg)
    if info:
        return run_registered(info["脚本"], rest, use_color,
                              int(get_setting("递归上限", cfg, 800) or 800))

    # 管理员通道
    if cmd in ("admin", "管理", "管理员", "sudo"):
        if run_admin is None:
            print(color("管理员模块加载失败", "31", use_color))
            return 1
        return run_admin(rest, use_color, HERE)

    if cmd in ("help", "-h", "--help", "帮助"):
        print(HELP)
        return 0

    if cmd in ("version", "-v", "--version", "版本"):
        from src import __version__
        print("Qiuli %s  (文件后缀 .ql)" % __version__)
        print("Python %s" % sys.version.split()[0])
        return 0

    if cmd in ("示例", "examples", "demo", "例子"):
        return list_examples(use_color)

    if cmd == "repl":
        from src.repl import REPL
        from src.interpreter import Interpreter
        REPL(Interpreter(base_dir=os.getcwd()), use_color).loop()
        return 0

    if cmd == "test":
        sys.path.insert(0, HERE)
        from tests.run_tests import main as run_tests
        return run_tests(rest)

    if cmd == "new":
        name = rest[0] if rest else "我的脚本"
        path = name if name.endswith(".ql") else name + ".ql"
        if os.path.exists(path):
            print(color("文件已存在：%s" % path, "31", use_color))
            return 1
        tpl = open(os.path.join(HERE, "examples", "模板.ql"), encoding="utf-8").read() \
            if os.path.exists(os.path.join(HERE, "examples", "模板.ql")) else TEMPLATE
        with open(path, "w", encoding="utf-8") as f:
            f.write(tpl)
        print(color("已创建 %s" % path, "32", use_color))
        return 0

    # ---------- 需要源文件的命令
    if cmd in ("run", "check", "ast", "tokens"):
        if not rest:
            print(color("缺少文件名", "31", use_color))
            return 1
        path = rest[0]
        args = rest[1:]
    else:
        path = cmd
        args = rest
        cmd = "run"

    # 当前目录找不到时，去项目自带的 examples/ 与 stdlib/ 里找，
    # 这样在任何目录都能直接写 "qiuli 01_你好世界.ql"
    # （可被管理员设置「自动找示例」关掉）
    if not os.path.exists(path):
        found = find_script(path) if get_setting("自动找示例", cfg, True) else None
        if found:
            print(color("（在项目目录中找到 %s）" % os.path.relpath(found, HERE),
                        "90", use_color))
            path = found
        else:
            print(color("找不到文件：%s" % path, "31", use_color))
            print(color("提示：可以先看看有哪些示例 —— qiuli 示例", "90", use_color))
            return 1

    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        print(color("读取失败：%s" % e, "31", use_color))
        return 1

    from src.errors import QiuliError, QiuliRuntimeError
    from src.interpreter import Interpreter
    from src.lexer import tokenize
    from src.parser import parse

    if cmd == "tokens":
        try:
            toks = tokenize(source, path)
        except QiuliError as e:
            print(e.render(use_color))
            return 1
        for t in toks:
            print("%-8s %-14s L%d:%d" % (t.type, repr(t.value), t.line, t.col))
        return 0

    if cmd == "ast":
        try:
            prog = parse(source, path)
        except QiuliError as e:
            print(e.render(use_color))
            return 1
        print(prog.dump())
        return 0

    if cmd == "check":
        t0 = time.perf_counter()
        try:
            parse(source, path)
        except QiuliError as e:
            print(e.render(use_color))
            return 1
        print(color("✔ 语法检查通过：%s（%.1f ms）"
                    % (path, (time.perf_counter() - t0) * 1000), "32", use_color))
        return 0

    # ---------- 运行
    interp = Interpreter(base_dir=os.path.dirname(os.path.abspath(path)), argv=args)
    if cfg is not None:
        interp.max_depth = int(get_setting("递归上限", cfg, 800) or 800)
    t0 = time.perf_counter()
    try:
        interp.run_file(path, args)
    except QiuliError as e:          # 语法错误
        print(e.render(use_color))
        return 1
    except QiuliRuntimeError as e:
        print(e.render(use_color))
        return 1
    except KeyboardInterrupt:
        print(color("\n（已中断）", "31", use_color))
        return 130
    except SystemExit as e:
        return int(e.code or 0)
    except Exception as e:                        # 兜底：解释器自身的意外
        if "--debug" in sys.argv:
            raise
        print(color("解释器内部错误：%s: %s" % (type(e).__name__, e), "31", use_color))
        print(color("（加 --debug 可以看到完整调用栈）", "90", use_color))
        return 1
    finally:
        if show_time:
            print(color("耗时 %.3f 秒" % (time.perf_counter() - t0), "90", use_color))
    return 0


TEMPLATE = '''# 我的第一个 Qiuli 程序
输出("你好，Qiuli！")

让 名字 = 输入("你叫什么名字？")
输出("欢迎你，${名字}！")
'''


if __name__ == "__main__":
    sys.exit(main())
