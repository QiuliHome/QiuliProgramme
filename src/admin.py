"""Qiuli 管理员通道

可以：
  · 给命令起别名、删除别名
  · 把任意 .ql 脚本注册成 qiuli 的子命令
  · 禁用 / 启用内置命令
  · 修改全局设置（彩色、递归上限、自动找示例…）
  · 设置管理员口令

配置保存在用户目录 ~/.qiuli/config.json（写不了就退回项目目录）。

用法：
    qiuli admin                      进入交互式管理通道
    qiuli admin 命令                 列出所有命令
    qiuli admin 别名 ls 示例          给「示例」起个别名 ls
    qiuli admin 注册 工具 a.ql        把脚本注册成命令
    qiuli admin 禁用 命令             禁用内置命令
    qiuli admin 配置 彩色 假
    qiuli admin 重置
"""

import json as _json
import os
import sys

CONFIG_VERSION = 1

DEFAULT_CONFIG = {
    "版本": CONFIG_VERSION,
    "别名": {},          # 别名 -> 目标命令
    "命令": {},          # 命令名 -> {"脚本": 绝对路径, "说明": 说明}
    "禁用": [],          # 被禁用的内置命令
    "设置": {
        "彩色": True,
        "递归上限": 800,
        "自动找示例": True,
    },
    "口令": "",          # 空表示不需要口令
}

BUILTIN_COMMANDS = [
    ("run", "运行脚本（默认命令，可省略）"),
    ("repl", "进入交互式环境"),
    ("check", "语法检查（不执行）"),
    ("ast", "打印语法树"),
    ("tokens", "打印词法单元"),
    ("test", "运行测试套件"),
    ("示例", "列出自带示例（examples/ 例子）"),
    ("new", "用模板新建脚本"),
    ("admin", "管理员通道（本通道）"),
    ("version", "版本信息"),
    ("help", "帮助"),
]

SETTINGS_DOC = {
    "彩色": "是否使用彩色输出（真 / 假）",
    "递归上限": "函数递归的最大层数（数字，默认 800）",
    "自动找示例": "找不到文件时自动去 examples/ 里找（真 / 假）",
}


# ---------------------------------------------------------------- 配置存取
def config_path():
    """优先用户目录，写不了就用项目目录"""
    home = os.path.expanduser("~")
    d = os.path.join(home, ".qiuli")
    try:
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "config.json")
        # 试探能否写入
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as f:
                f.write("")
        return p
    except Exception:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(here, ".qiuli_config.json")


def load_config():
    p = config_path()
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return _json.loads(_json.dumps(DEFAULT_CONFIG)), p
    try:
        with open(p, "r", encoding="utf-8") as f:
            cfg = _json.load(f)
    except Exception:
        return _json.loads(_json.dumps(DEFAULT_CONFIG)), p
    # 补齐缺失字段（兼容旧配置）
    for k, v in DEFAULT_CONFIG.items():
        if k not in cfg:
            cfg[k] = _json.loads(_json.dumps(v))
        elif isinstance(v, dict) and isinstance(cfg[k], dict):
            for kk, vv in v.items():
                cfg[k].setdefault(kk, vv)
    return cfg, p


def save_config(cfg, path=None):
    p = path or config_path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            _json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print("配置保存失败：%s" % e)
        return False


# ---------------------------------------------------------------- 查询
def resolve_alias(name, cfg=None):
    """把别名解析成真正的命令名（最多 5 层，防止成环）"""
    cfg = cfg if cfg is not None else load_config()[0]
    seen = set()
    cur = name
    for _ in range(5):
        if cur in seen:
            return cur
        seen.add(cur)
        nxt = cfg["别名"].get(cur)
        if not nxt or nxt == cur:
            return cur
        cur = nxt
    return cur


def is_disabled(name, cfg=None):
    cfg = cfg if cfg is not None else load_config()[0]
    name = resolve_alias(name, cfg)
    return name in cfg["禁用"]


def get_script_command(name, cfg=None):
    """返回注册命令的信息 dict，未注册则返回 None"""
    cfg = cfg if cfg is not None else load_config()[0]
    name = resolve_alias(name, cfg)
    return cfg["命令"].get(name)


def get_setting(key, cfg=None, default=None):
    cfg = cfg if cfg is not None else load_config()[0]
    return cfg["设置"].get(key, default)


def check_pin(cfg, use_color=True, action="进入管理员通道"):
    """口令校验；没设置口令时直接放行"""
    pin = cfg.get("口令") or ""
    if not pin:
        return True
    try:
        given = input("请输入管理员口令：")
    except EOFError:
        return False
    if given.strip() == pin:
        return True
    print(color("口令不正确，操作已取消（%s）" % action, "31", use_color))
    return False


def color(text, code, enabled=True):
    return "\033[%sm%s\033[0m" % (code, text) if enabled else text


# ---------------------------------------------------------------- 非交互子命令
def cmd_list(cfg, use_color=True):
    print(color("\n  内置命令", "36", use_color))
    for name, desc in BUILTIN_COMMANDS:
        mark = color("（已禁用）", "31", use_color) if is_disabled(name, cfg) else ""
        print("    %-12s %s %s" % (name, desc, mark))

    if cfg["别名"]:
        print(color("\n  别名", "36", use_color))
        for a, t in sorted(cfg["别名"].items()):
            print("    %-12s → %s" % (a, t))

    if cfg["命令"]:
        print(color("\n  注册的脚本命令", "36", use_color))
        for n, info in sorted(cfg["命令"].items()):
            print("    %-12s %s" % (n, info.get("脚本", "")))
            if info.get("说明"):
                print("    %-12s   %s" % ("", info["说明"]))

    print(color("\n  共 %d 个内置命令、%d 个别名、%d 个脚本命令\n"
                % (len(BUILTIN_COMMANDS), len(cfg["别名"]), len(cfg["命令"])),
                "90", use_color))
    return 0


def cmd_alias(cfg, path, args, use_color=True):
    if len(args) < 2:
        print(color("用法：别名 <新名字> <原命令>    例如：别名 ls 示例", "31", use_color))
        return 1
    new, target = args[0], args[1]
    cfg["别名"][new] = target
    save_config(cfg, path)
    print(color("✔ 已设置：%s → %s" % (new, target), "32", use_color))
    return 0


def cmd_unalias(cfg, path, args, use_color=True):
    if not args:
        print(color("用法：删除别名 <名字>", "31", use_color))
        return 1
    n = args[0]
    if n in cfg["别名"]:
        del cfg["别名"][n]
        save_config(cfg, path)
        print(color("✔ 已删除别名 %s" % n, "32", use_color))
        return 0
    print(color("没有这个别名：%s" % n, "31", use_color))
    return 1


def cmd_register(cfg, path, args, use_color=True, base_dir=None):
    if len(args) < 2:
        print(color("用法：注册 <命令名> <脚本.ql> [说明]", "31", use_color))
        return 1
    name, script = args[0], args[1]
    desc = " ".join(args[2:])
    full = script if os.path.isabs(script) else os.path.abspath(
        os.path.join(base_dir or os.getcwd(), script))
    if not os.path.exists(full):
        print(color("找不到脚本：%s" % full, "31", use_color))
        return 1
    cfg["命令"][name] = {"脚本": full, "说明": desc}
    save_config(cfg, path)
    print(color("✔ 已注册命令 %s → %s" % (name, full), "32", use_color))
    print(color("  现在可以直接用：qiuli %s" % name, "90", use_color))
    return 0


def cmd_unregister(cfg, path, args, use_color=True):
    if not args:
        print(color("用法：注销 <命令名>", "31", use_color))
        return 1
    n = args[0]
    if n in cfg["命令"]:
        del cfg["命令"][n]
        save_config(cfg, path)
        print(color("✔ 已注销 %s" % n, "32", use_color))
        return 0
    print(color("没有这个命令：%s" % n, "31", use_color))
    return 1


def cmd_disable(cfg, path, args, use_color=True):
    if not args:
        print(color("用法：禁用 <命令名>", "31", use_color))
        return 1
    n = resolve_alias(args[0], cfg)
    if n not in cfg["禁用"]:
        cfg["禁用"].append(n)
        save_config(cfg, path)
    print(color("✔ 已禁用 %s" % n, "32", use_color))
    return 0


def cmd_enable(cfg, path, args, use_color=True):
    if not args:
        print(color("用法：启用 <命令名>", "31", use_color))
        return 1
    n = resolve_alias(args[0], cfg)
    if n in cfg["禁用"]:
        cfg["禁用"].remove(n)
        save_config(cfg, path)
    print(color("✔ 已启用 %s" % n, "32", use_color))
    return 0


def cmd_setting(cfg, path, args, use_color=True):
    if not args:
        print(color("\n  当前设置", "36", use_color))
        for k, v in cfg["设置"].items():
            print("    %-12s %s" % (k, v))
        print(color("\n  可选项：" + "、".join(SETTINGS_DOC.keys()), "90", use_color))
        print(color("  修改：配置 <键> <值>\n", "90", use_color))
        return 0
    if len(args) < 2:
        print(color("用法：配置 <键> <值>", "31", use_color))
        return 1
    k, raw = args[0], args[1]
    if k not in SETTINGS_DOC:
        print(color("没有这个设置项：%s（可选：%s）" % (k, "、".join(SETTINGS_DOC.keys())),
                    "31", use_color))
        return 1
    if raw in ("真", "true", "True", "1", "是", "开"):
        val = True
    elif raw in ("假", "false", "False", "0", "否", "关"):
        val = False
    else:
        try:
            val = int(raw)
        except ValueError:
            val = raw
    cfg["设置"][k] = val
    save_config(cfg, path)
    print(color("✔ 已设置 %s = %s" % (k, val), "32", use_color))
    return 0


def cmd_reset(cfg, path, use_color=True):
    fresh = _json.loads(_json.dumps(DEFAULT_CONFIG))
    save_config(fresh, path)
    cfg.clear()
    cfg.update(fresh)
    print(color("✔ 已恢复默认配置", "32", use_color))
    return 0


def cmd_pin(cfg, path, args, use_color=True):
    if not args:
        cfg["口令"] = ""
        save_config(cfg, path)
        print(color("✔ 已清除口令（以后进入管理通道不用输入）", "32", use_color))
        return 0
    cfg["口令"] = args[0]
    save_config(cfg, path)
    print(color("✔ 口令已设置", "32", use_color))
    return 0


# ---------------------------------------------------------------- 交互通道
HELP_TEXT = """
  管理员通道可用指令

    命令列表                      查看所有命令（内置 / 别名 / 脚本命令）
    别名 <新名> <原命令>           给命令起别名      例：别名 ls 示例
    删除别名 <名字>                删除一个别名
    注册 <命令名> <脚本.ql> [说明]  把脚本注册成 qiuli 子命令
    注销 <命令名>                  取消注册的脚本命令
    禁用 <命令名>                  禁用某个内置命令
    启用 <命令名>                  恢复被禁用的命令
    配置 [键] [值]                 查看或修改全局设置
    口令 [新口令]                  设置口令（不带参数＝清除）
    重置                          恢复出厂设置
    帮助                          显示本帮助
    退出                          离开管理通道

  也可以不进交互模式，直接：
    qiuli admin 命令
    qiuli admin 别名 ls 示例
    qiuli admin 注册 工具 我的工具.ql
    qiuli admin 配置 彩色 假
"""


def admin_loop(use_color=True, base_dir=None):
    cfg, path = load_config()
    if not check_pin(cfg, use_color):
        return 1

    print(color("\n  ┌──────────────────────────────────┐", "93", use_color))
    print(color("  │   Qiuli 管理员通道                │", "93", use_color))
    print(color("  └──────────────────────────────────┘", "93", use_color))
    print(color("  配置文件：%s" % path, "90", use_color))
    print(color("  输入 帮助 看能做什么，退出 离开\n", "90", use_color))

    while True:
        try:
            line = input("admin> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        parts = line.split()
        cmd, args = parts[0], parts[1:]

        if cmd in ("退出", "exit", "quit", "q"):
            break
        elif cmd in ("帮助", "help", "?"):
            print(HELP_TEXT)
        elif cmd in ("命令列表", "命令", "list"):
            cmd_list(cfg, use_color)
        elif cmd in ("别名", "alias"):
            cmd_alias(cfg, path, args, use_color)
        elif cmd in ("删除别名", "unalias"):
            cmd_unalias(cfg, path, args, use_color)
        elif cmd in ("注册", "register"):
            cmd_register(cfg, path, args, use_color, base_dir)
        elif cmd in ("注销", "unregister"):
            cmd_unregister(cfg, path, args, use_color)
        elif cmd in ("禁用", "disable"):
            cmd_disable(cfg, path, args, use_color)
        elif cmd in ("启用", "enable"):
            cmd_enable(cfg, path, args, use_color)
        elif cmd in ("配置", "setting", "设置"):
            cmd_setting(cfg, path, args, use_color)
        elif cmd in ("口令", "pin", "密码"):
            cmd_pin(cfg, path, args, use_color)
        elif cmd in ("重置", "reset"):
            cmd_reset(cfg, path, use_color)
            cfg, path = load_config()
        else:
            print(color("看不懂「%s」，输入 帮助 看看能做什么" % cmd, "31", use_color))
    return 0


# ---------------------------------------------------------------- 入口
def run_admin(args, use_color=True, base_dir=None):
    """qiuli admin ... 的入口"""
    cfg, path = load_config()

    if not args:
        return admin_loop(use_color, base_dir)

    cmd, rest = args[0], args[1:]
    need_pin = cmd not in ("命令", "命令列表", "list", "帮助", "help")
    if need_pin and not check_pin(cfg, use_color, "执行 %s" % cmd):
        return 1

    table = {
        "命令": cmd_list, "命令列表": cmd_list, "list": cmd_list,
    }
    if cmd in table:
        return table[cmd](cfg, use_color)
    if cmd in ("帮助", "help"):
        print(HELP_TEXT)
        return 0
    if cmd in ("别名", "alias"):
        return cmd_alias(cfg, path, rest, use_color)
    if cmd in ("删除别名", "unalias"):
        return cmd_unalias(cfg, path, rest, use_color)
    if cmd in ("注册", "register"):
        return cmd_register(cfg, path, rest, use_color, base_dir)
    if cmd in ("注销", "unregister"):
        return cmd_unregister(cfg, path, rest, use_color)
    if cmd in ("禁用", "disable"):
        return cmd_disable(cfg, path, rest, use_color)
    if cmd in ("启用", "enable"):
        return cmd_enable(cfg, path, rest, use_color)
    if cmd in ("配置", "设置", "setting"):
        return cmd_setting(cfg, path, rest, use_color)
    if cmd in ("口令", "密码", "pin"):
        return cmd_pin(cfg, path, rest, use_color)
    if cmd in ("重置", "reset"):
        return cmd_reset(cfg, path, use_color)

    print(color("管理员通道没有这个指令：%s（试试 qiuli admin 帮助）" % cmd, "31", use_color))
    return 1
