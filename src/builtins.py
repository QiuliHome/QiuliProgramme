"""Qiuli 标准库：内置函数、内置类型的成员、内置模块。"""

import json as _json
import math as _math
import os as _os
import platform as _platform
import random as _random
import subprocess as _subprocess
import sys as _sys
import time as _time

from .environment import UNDEFINED
from .errors import QiuliRuntimeError
from .objects import (NativeFunction, QlError, QlModule, QlRange, ql_str,
                      ql_type, truthy)

# ================================================================== 工具


def _err(msg):
    return QiuliRuntimeError(msg, "<内置>", 0, None)


def _need(v, *types, name="参数"):
    if not isinstance(v, types):
        want = "/".join(t.__name__ for t in types)
        raise _err("%s 类型不对：期望 %s，实际是 %s" % (name, want, ql_type(v)))
    return v


def _num(v, name="参数"):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise _err("%s 必须是数字，实际是 %s" % (name, ql_type(v)))
    return v


def _seq(v, name="参数"):
    if not isinstance(v, (list, str)):
        raise _err("%s 必须是列表或字符串，实际是 %s" % (name, ql_type(v)))
    return v


# ================================================================== 内置类型成员
TYPE_ATTRS = {
    list: {
        "长度": len,
        "length": len,
    },
    str: {
        "长度": len,
        "length": len,
    },
    dict: {
        "长度": len,
        "length": len,
        "键": lambda d: list(d.keys()),
        "keys": lambda d: list(d.keys()),
        "值": lambda d: list(d.values()),
        "values": lambda d: list(d.values()),
        "项": lambda d: [[k, v] for k, v in d.items()],
        "items": lambda d: [[k, v] for k, v in d.items()],
    },
}

LIST_METHODS = {
    "追加": lambda o, *a: (o.append(a[0]) if a else None) or o,
    "push": lambda o, *a: (o.append(a[0]) if a else None) or o,
    "弹出": lambda o, *a: o.pop() if not a else o.pop(int(a[0])),
    "pop": lambda o, *a: o.pop() if not a else o.pop(int(a[0])),
    "插入": lambda o, *a: o.insert(int(a[0]), a[1]) or o,
    "删除": lambda o, *a: o.remove(a[0]) or o,
    "清空": lambda o, *a: o.clear() or o,
    "包含": lambda o, *a: a[0] in o,
    "查找": lambda o, *a: o.index(a[0]) if a[0] in o else -1,
    "计数": lambda o, *a: o.count(a[0]),
    "排序": lambda o, *a: (o.sort(key=_key_of(a[0]) if a else None) or o),
    "反转": lambda o, *a: o.reverse() or o,
    "复制": lambda o, *a: list(o),
    "映射": lambda o, *a: [_call1(a[0], x) for x in o],
    "过滤": lambda o, *a: [x for x in o if truthy(_call1(a[0], x))],
    "归约": lambda o, *a: _reduce(o, a[0], a[1] if len(a) > 1 else None),
    "每个": lambda o, *a: ([_call1(a[0], x) for x in o], None)[1],
    "连接": lambda o, *a: (a[0] if a else "").join(ql_str(x) for x in o),
    "求和": lambda o, *a: sum(_num(x) for x in o),
    "最大": lambda o, *a: max(o) if o else None,
    "最小": lambda o, *a: min(o) if o else None,
    "切片": lambda o, *a: o[_i(a[0]) if a else None:_i(a[1]) if len(a) > 1 else None],
    "去重": lambda o, *a: _unique(o),
    "展平": lambda o, *a: _flatten(o),
    "最后一个": lambda o, *a: o[-1] if o else None,
    "第一个": lambda o, *a: o[0] if o else None,
}

STR_METHODS = {
    "大写": lambda o, *a: o.upper(),
    "小写": lambda o, *a: o.lower(),
    "去空白": lambda o, *a: o.strip(a[0] if a else None),
    "分割": lambda o, *a: o.split(a[0] if a else None),
    "替换": lambda o, *a: o.replace(a[0], a[1]),
    "包含": lambda o, *a: a[0] in o,
    "开头": lambda o, *a: o.startswith(a[0]),
    "结尾": lambda o, *a: o.endswith(a[0]),
    "查找": lambda o, *a: o.find(a[0]),
    "计数": lambda o, *a: o.count(a[0]),
    "子串": lambda o, *a: o[_i(a[0]):_i(a[1]) if len(a) > 1 else None],
    "重复": lambda o, *a: o * int(a[0]),
    "字符": lambda o, *a: list(o),
    "转数字": lambda o, *a: _to_number(o),
    "反转": lambda o, *a: o[::-1],
    "填充": lambda o, *a: o.ljust(int(a[0]), a[1] if len(a) > 1 else " "),
    "右填充": lambda o, *a: o.rjust(int(a[0]), a[1] if len(a) > 1 else " "),
    "居中": lambda o, *a: o.center(int(a[0]), a[1] if len(a) > 1 else " "),
    "是数字串": lambda o, *a: _is_num_str(o),
    "标题化": lambda o, *a: o.title(),
    "交换大小写": lambda o, *a: o.swapcase(),
}

DICT_METHODS = {
    "取": lambda o, *a: o.get(a[0], a[1] if len(a) > 1 else None),
    "get": lambda o, *a: o.get(a[0], a[1] if len(a) > 1 else None),
    "包含": lambda o, *a: a[0] in o,
    "删除": lambda o, *a: o.pop(a[0], None),
    "复制": lambda o, *a: dict(o),
    "合并": lambda o, *a: {**o, **(a[0] if a else {})},
    "更新": lambda o, *a: (o.update(a[0]) or o),
    "映射": lambda o, *a: {k: _call1(a[0], v) for k, v in o.items()},
}

TYPE_METHODS = {list: LIST_METHODS, str: STR_METHODS, dict: DICT_METHODS}


def _i(v):
    return int(v) if v is not None else None


def _key_of(f):
    if callable(f):
        return lambda x: _call1(f, x)
    return None


def _call1(f, x):
    """调用 Qiuli 一元函数（可能是 QlFunction / NativeFunction）"""
    from .interpreter import Interpreter
    if isinstance(f, NativeFunction):
        return f.fn(x)
    # 延迟导入避免循环
    interp = _current_interp
    if interp is None:
        raise _err("无法调用函数")
    return interp.call_value(f, [x], {}, 0, None)


def _reduce(o, f, init):
    it = list(o)
    if init is None:
        if not it:
            return None
        acc = it[0]
        rest = it[1:]
    else:
        acc = init
        rest = it
    for x in rest:
        acc = _call2(f, acc, x)
    return acc


def _call2(f, a, b):
    if isinstance(f, NativeFunction):
        return f.fn(a, b)
    interp = _current_interp
    if interp is None:
        raise _err("无法调用函数")
    return interp.call_value(f, [a, b], {}, 0, None)


def _unique(o):
    seen = set()
    out = []
    for x in o:
        k = (type(x).__name__, x) if isinstance(x, (int, float, str, bool)) else id(x)
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def _flatten(o):
    out = []
    for x in o:
        if isinstance(x, list):
            out.extend(_flatten(x))
        else:
            out.append(x)
    return out


def _to_number(s):
    s = s.strip()
    try:
        if "." in s or "e" in s.lower():
            return float(s)
        return int(s)
    except ValueError:
        return None


def _reverse(x):
    x = _seq(x)
    if isinstance(x, str):
        return x[::-1]
    return list(reversed(x))


def _call0(f):
    if isinstance(f, NativeFunction):
        return f.fn()
    if _current_interp is None:
        raise _err("无法调用函数")
    return _current_interp.call_value(f, [], {}, 0, None)


def _is_num_str(s):
    return _to_number(s) is not None


_current_interp = None


def get_member(obj, name):
    """内置类型（列表/字符串/字典）的成员访问"""
    from .objects import BuiltinMethod
    for typ, table in TYPE_ATTRS.items():
        if isinstance(obj, typ) and not isinstance(obj, (QlRange,)):
            if name in table:
                return table[name](obj)
            m = TYPE_METHODS[typ].get(name)
            if m:
                return BuiltinMethod(obj, name, m)
            return None
    return None


# ================================================================== 内置模块
def _mod_math():
    return {
        "圆周率": _math.pi, "PI": _math.pi, "pi": _math.pi,
        "自然常数": _math.e, "E": _math.e, "e": _math.e,
        "无穷": float("inf"), "无穷大": float("inf"),
        "绝对值": NativeFunction("绝对值", lambda x: abs(_num(x)), 1),
        "平方根": NativeFunction("平方根", lambda x: _math.sqrt(_num(x)), 1),
        "幂": NativeFunction("幂", lambda a, b: _num(a) ** _num(b), 2),
        "正弦": NativeFunction("正弦", lambda x: _math.sin(_num(x)), 1),
        "余弦": NativeFunction("余弦", lambda x: _math.cos(_num(x)), 1),
        "正切": NativeFunction("正切", lambda x: _math.tan(_num(x)), 1),
        "反正弦": NativeFunction("反正弦", lambda x: _math.asin(_num(x)), 1),
        "反余弦": NativeFunction("反余弦", lambda x: _math.acos(_num(x)), 1),
        "反正切": NativeFunction("反正切", lambda x: _math.atan(_num(x)), 1),
        "对数": NativeFunction("对数", lambda x, b=_math.e: _math.log(_num(x), _num(b)), -1),
        "常用对数": NativeFunction("常用对数", lambda x: _math.log10(_num(x)), 1),
        "上取整": NativeFunction("上取整", lambda x: _math.ceil(_num(x)), 1),
        "下取整": NativeFunction("下取整", lambda x: _math.floor(_num(x)), 1),
        "四舍五入": NativeFunction("四舍五入", lambda x, n=0: round(_num(x), int(n)), -1),
        "取整": NativeFunction("取整", lambda x: int(_num(x)), 1),
        "阶乘": NativeFunction("阶乘", lambda x: _math.factorial(int(_num(x))), 1),
        "最大公约数": NativeFunction("最大公约数", lambda a, b: _math.gcd(int(a), int(b)), 2),
        "转弧度": NativeFunction("转弧度", lambda x: _math.radians(_num(x)), 1),
        "转角度": NativeFunction("转角度", lambda x: _math.degrees(_num(x)), 1),
        "最大": NativeFunction("最大", lambda *a: max(a) if a else None, -1),
        "最小": NativeFunction("最小", lambda *a: min(a) if a else None, -1),
        "求和": NativeFunction("求和", lambda x: sum(_num(i) for i in _need(x, list)), 1),
        "是质数": NativeFunction("是质数", _is_prime, 1),
        "斐波那契": NativeFunction("斐波那契", _fib, 1),
    }


def _is_prime(n):
    n = int(_num(n))
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def _fib(n):
    n = int(_num(n))
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _mod_time():
    return {
        "时间戳": NativeFunction("时间戳", lambda: _time.time(), 0),
        "毫秒": NativeFunction("毫秒", lambda: int(_time.time() * 1000), 0),
        "睡眠": NativeFunction("睡眠", lambda s: (_time.sleep(_num(s)), None)[1], 1),
        "现在": NativeFunction("现在", lambda: _time.strftime("%Y-%m-%d %H:%M:%S"), 0),
        "今天": NativeFunction("今天", lambda: _time.strftime("%Y-%m-%d"), 0),
        "年": NativeFunction("年", lambda: _time.localtime().tm_year, 0),
        "月": NativeFunction("月", lambda: _time.localtime().tm_mon, 0),
        "日": NativeFunction("日", lambda: _time.localtime().tm_mday, 0),
        "时": NativeFunction("时", lambda: _time.localtime().tm_hour, 0),
        "分": NativeFunction("分", lambda: _time.localtime().tm_min, 0),
        "秒": NativeFunction("秒", lambda: _time.localtime().tm_sec, 0),
        "星期": NativeFunction("星期", lambda: int(_time.strftime("%w")), 0),
        "格式化": NativeFunction("格式化", _fmt_time, -1),
        "计时": NativeFunction("计时", lambda f: _timing(f), 1),
    }


def _fmt_time(ts=None, fmt="%Y-%m-%d %H:%M:%S"):
    t = _time.localtime(_num(ts) if ts is not None else _time.time())
    return _time.strftime(fmt, t)


def _timing(f):
    t0 = _time.perf_counter()
    _call0(f)
    return round((_time.perf_counter() - t0) * 1000, 3)


def _mod_random():
    return {
        "整数": NativeFunction("整数", lambda a=0, b=None: _random.randint(int(a), int(b)) if b is not None else _random.randint(0, int(a)), -1),
        "浮点": NativeFunction("浮点", lambda a=0.0, b=1.0: _random.uniform(_num(a), _num(b)), -1),
        "随机": NativeFunction("随机", lambda: _random.random(), 0),
        "选择": NativeFunction("选择", lambda x: _random.choice(_need(x, list)), 1),
        "打乱": NativeFunction("打乱", lambda x: (_random.shuffle(_need(x, list)) or x), 1),
        "抽样": NativeFunction("抽样", lambda x, k: _random.sample(_need(x, list), int(k)), 2),
        "种子": NativeFunction("种子", lambda s: (_random.seed(int(s)), None)[1], 1),
    }


def _mod_fs():
    return {
        "读": NativeFunction("读", _read_file, 1),
        "读文本": NativeFunction("读文本", _read_file, 1),
        "写": NativeFunction("写", _write_file, 2),
        "追加": NativeFunction("追加", _append_file, 2),
        "存在": NativeFunction("存在", lambda p: _os.path.exists(ql_str(p)), 1),
        "是目录": NativeFunction("是目录", lambda p: _os.path.isdir(ql_str(p)), 1),
        "删除": NativeFunction("删除", lambda p: (_os.remove(ql_str(p)), True)[1], 1),
        "列出": NativeFunction("列出", lambda p=".": _os.listdir(ql_str(p)), 1),
        "建目录": NativeFunction("建目录", lambda p: (_os.makedirs(ql_str(p), exist_ok=True), True)[1], 1),
        "大小": NativeFunction("大小", lambda p: _os.path.getsize(ql_str(p)), 1),
        "绝对路径": NativeFunction("绝对路径", lambda p: _os.path.abspath(ql_str(p)), 1),
        "改名": NativeFunction("改名", lambda a, b: (_os.rename(ql_str(a), ql_str(b)), True)[1], 2),
        "当前目录": NativeFunction("当前目录", lambda: _os.getcwd(), 0),
        "读行": NativeFunction("读行", lambda p: _read_file(p).split("\n"), 1),
    }


def _read_file(p):
    p = ql_str(p)
    if not _os.path.exists(p):
        raise _err("文件不存在：%s" % p)
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def _write_file(p, content):
    p = ql_str(p)
    d = _os.path.dirname(p)
    if d and not _os.path.isdir(d):
        _os.makedirs(d, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(ql_str(content))
    return True


def _append_file(p, content):
    with open(ql_str(p), "a", encoding="utf-8") as f:
        f.write(ql_str(content))
    return True


def _mod_json():
    return {
        "解析": NativeFunction("解析", lambda s: _json.loads(ql_str(s)), 1),
        "生成": NativeFunction("生成", lambda x, indent=2: _json.dumps(_jsonable(x), ensure_ascii=False, indent=int(indent)), -1),
        "压缩": NativeFunction("压缩", lambda x: _json.dumps(_jsonable(x), ensure_ascii=False, separators=(",", ":")), 1),
    }


def _jsonable(x):
    if isinstance(x, dict):
        return {ql_str(k) if not isinstance(k, str) else k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_jsonable(i) for i in x]
    if x is None or isinstance(x, (bool, int, float, str)):
        return x
    return ql_str(x)


def _mod_sys():
    return {
        "参数": [],
        "平台": _platform.system() + " " + _platform.release(),
        "退出": NativeFunction("退出", lambda code=0: _sys.exit(int(code)), -1),
        "命令": NativeFunction("命令", lambda c: _run_cmd(c), 1),
        "环境变量": NativeFunction("环境变量", lambda k=None: _os.environ.get(ql_str(k)) if k else dict(_os.environ), -1),
        "清屏": NativeFunction("清屏", lambda: (_os.system("cls" if _os.name == "nt" else "clear"), None)[1], 0),
        "版本": "1.0.0",
        "语言": "Qiuli",
    }


def _run_cmd(c):
    try:
        r = _subprocess.run(ql_str(c), shell=True, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=60)
        return {"退出码": r.returncode, "输出": r.stdout, "错误": r.stderr}
    except Exception as e:
        return {"退出码": -1, "输出": "", "错误": str(e)}


def _mod_str():
    return {
        "格式化": NativeFunction("格式化", lambda fmt, *a: _py_format(fmt, a), -1),
        "连接": NativeFunction("连接", lambda x, sep="": sep.join(ql_str(i) for i in _need(x, list)), -1),
        "重复": NativeFunction("重复", lambda s, n: ql_str(s) * int(n), 2),
        "字符码": NativeFunction("字符码", lambda s: ord(ql_str(s)[0]), 1),
        "码转字符": NativeFunction("码转字符", lambda n: chr(int(n)), 1),
        "补零": NativeFunction("补零", lambda s, n: ql_str(s).zfill(int(n)), 2),
        "去空白": NativeFunction("去空白", lambda s: ql_str(s).strip(), 1),
        "包含": NativeFunction("包含", lambda s, sub: ql_str(sub) in ql_str(s), 2),
        "长度": NativeFunction("长度", lambda s: len(ql_str(s)), 1),
    }


def _py_format(fmt, args):
    fmt = ql_str(fmt)
    try:
        return fmt.format(*[ql_str(a) for a in args])
    except Exception:
        try:
            return fmt % tuple(ql_str(a) for a in args)
        except Exception as e:
            raise _err("格式化字符串失败：%s" % e)


def _mod_term():
    def wrap(code):
        return lambda s: "\033[%sm%s\033[0m" % (code, ql_str(s))
    return {
        "红": NativeFunction("红", wrap("31"), 1),
        "绿": NativeFunction("绿", wrap("32"), 1),
        "黄": NativeFunction("黄", wrap("33"), 1),
        "蓝": NativeFunction("蓝", wrap("34"), 1),
        "紫": NativeFunction("紫", wrap("35"), 1),
        "青": NativeFunction("青", wrap("36"), 1),
        "灰": NativeFunction("灰", wrap("90"), 1),
        "粗体": NativeFunction("粗体", wrap("1"), 1),
        "下划线": NativeFunction("下划线", wrap("4"), 1),
        "反色": NativeFunction("反色", wrap("7"), 1),
    }


BUILTIN_MODULES = {
    "数学": _mod_math, "math": _mod_math,
    "时间": _mod_time, "time": _mod_time,
    "随机": _mod_random, "random": _mod_random,
    "文件": _mod_fs, "fs": _mod_fs, "file": _mod_fs,
    "JSON": _mod_json, "json": _mod_json, "Json": _mod_json,
    "系统": _mod_sys, "sys": _mod_sys,
    "字符串": _mod_str, "str": _mod_str,
    "终端": _mod_term, "term": _mod_term,
}

_module_cache = {}


def get_builtin_module(name):
    name = ql_str(name)
    builder = BUILTIN_MODULES.get(name)
    if builder is None:
        return None
    if name not in _module_cache:
        _module_cache[name] = QlModule(name, builder(), "<内置模块>")
    return _module_cache[name]


# ================================================================== 内置函数
def register_builtins(env, interp):
    """把内置函数注入全局环境（中英双语名）"""
    global _current_interp
    _current_interp = interp

    def out(*args):
        s = " ".join(interp.str_of(a) for a in args)
        interp.stdout.write(s + "\n")
        interp.stdout.flush()
        return None

    def write_(*args):
        s = " ".join(interp.str_of(a) for a in args)
        interp.stdout.write(s)
        interp.stdout.flush()
        return None

    def input_(prompt=""):
        try:
            return input(ql_str(prompt))
        except EOFError:
            return None

    def sort_list(x, key=None):
        lst = list(_need(x, list))
        try:
            if key is not None:
                lst.sort(key=lambda v: _call1(key, v))
            else:
                lst.sort(key=_sort_key)
        except TypeError:
            raise _err("排序失败：列表中的元素类型不一致")
        return lst

    def assert_(cond, msg="断言失败"):
        if not truthy(cond):
            raise _err(ql_str(msg))
        return True

    def help_(name=None):
        if name is None:
            lines = ["Qiuli 内置函数一览："]
            items = sorted(set(BUILTIN_FN_NAMES))
            lines.append("  " + "、".join(items))
            lines.append("")
            lines.append("内置模块：" + "、".join(
                [k for k in BUILTIN_MODULES.keys() if not k.isascii()]))
            lines.append("提示：帮助(\"某个名字\") 可查看用法")
            return "\n".join(lines)
        n = ql_str(name)
        d = BUILTIN_DOCS.get(n)
        if d is None:
            return "没有找到 %r 的帮助" % n
        return "%s：%s\n  用法：%s" % (n, d[0], d[1])

    defs = {
        # 输入输出
        "输出": (out, ["print", "打印", "说"]),
        "写": (write_, ["write"]),
        "输入": (input_, ["input", "读输入"]),
        # 类型转换
        "字符串": (lambda x: interp.str_of(x), ["str", "转字符串"]),
        "数字": (lambda x: _to_number(ql_str(x)) if isinstance(x, str) else (x if isinstance(x, (int, float)) else None), ["num", "转数字"]),
        "整数": (lambda x=0: int(_num(x)) if not isinstance(x, str) else int(float(x)), ["int", "转整数"]),
        "浮点": (lambda x=0.0: float(_num(x)) if not isinstance(x, str) else float(x), ["float", "转浮点"]),
        "布尔": (lambda x=False: truthy(x), ["bool", "转布尔"]),
        "列表": (lambda x=None: list(x) if isinstance(x, (list, str)) else ([x] if x is not None else []), ["list", "转列表"]),
        "字典": (lambda *a: dict(a[0]) if a and isinstance(a[0], dict) else {}, ["dict", "转字典"]),
        # 查询
        "长度": (_seq_or_dict, ["len", "个数"]),
        "类型": (lambda x: ql_type(x), ["type"]),
        # 数学
        "绝对值": (lambda x: abs(_num(x)), ["abs"]),
        "平方根": (lambda x: _math.sqrt(_num(x)), ["sqrt"]),
        "幂": (lambda a, b=2: _num(a) ** _num(b), ["pow"]),
        "四舍五入": (lambda x, n=0: round(_num(x), int(n)), ["round"]),
        "上取整": (lambda x: _math.ceil(_num(x)), ["ceil"]),
        "下取整": (lambda x: _math.floor(_num(x)), ["floor"]),
        "最大": (lambda *a: max(*a) if len(a) > 1 else max(_need(a[0], list)), ["max"]),
        "最小": (lambda *a: min(*a) if len(a) > 1 else min(_need(a[0], list)), ["min"]),
        "求和": (lambda x: sum(_num(i) for i in _need(x, list)), ["sum"]),
        # 序列
        "范围": (lambda a, b=None, s=1: _range_list(a, b, s), ["range"]),
        "区间": (lambda a, b: QlRange(int(a), int(b)), ["rangeobj"]),
        "枚举": (lambda x: [[i, v] for i, v in enumerate(_need(x, list))], ["enumerate"]),
        "压缩": (lambda *xs: [list(t) for t in zip(*[_need(x, list) for x in xs])], ["zip"]),
        "映射": (lambda f, x: [_call1(f, v) for v in _need(x, list)], ["map"]),
        "过滤": (lambda f, x: [v for v in _need(x, list) if truthy(_call1(f, v))], ["filter"]),
        "归约": (lambda f, x, init=None: _reduce(_need(x, list), f, init), ["reduce"]),
        "排序": (sort_list, ["sorted"]),
        "反转": (_reverse, ["reversed"]),
        "切片": (lambda x, a=None, b=None: _seq(x)[_i(a):_i(b)], ["slice"]),
        "包含": (lambda x, v: v in x if isinstance(x, (list, str, dict)) else False, ["contains", "in"]),
        "追加": (lambda x, *v: (x.extend(v) or x) if isinstance(x, list) else None, ["push"]),
        "弹出": (lambda x, i=-1: x.pop() if isinstance(x, list) and i == -1 else x.pop(int(i)), ["pop"]),
        "去重": (lambda x: _unique(_need(x, list)), ["unique"]),
        "展平": (lambda x: _flatten(_need(x, list)), ["flatten"]),
        "连接": (lambda x, sep="": sep.join(ql_str(i) for i in _need(x, list)), ["join"]),
        "分割": (lambda s, sep=None: ql_str(s).split(ql_str(sep) if sep else None), ["split"]),
        # 字符串
        "替换": (lambda s, a, b: ql_str(s).replace(ql_str(a), ql_str(b)), ["replace"]),
        "去空白": (lambda s: ql_str(s).strip(), ["trim"]),
        "大写": (lambda s: ql_str(s).upper(), ["upper"]),
        "小写": (lambda s: ql_str(s).lower(), ["lower"]),
        "查找": (lambda s, sub: ql_str(s).find(ql_str(sub)), ["find"]),
        "计数": (lambda x, v: _seq(x).count(v), ["count"]),
        "字符码": (lambda s: ord(ql_str(s)[0]), ["ord"]),
        "码转字符": (lambda n: chr(int(n)), ["chr"]),
        "补零": (lambda s, n: ql_str(s).zfill(int(n)), ["zfill"]),
        "居中": (lambda s, n, ch=" ": ql_str(s).center(int(n), ql_str(ch)[0:1] or " "), ["center"]),
        # 文件 / JSON
        "读文件": (_read_file, ["readfile"]),
        "写文件": (_write_file, ["writefile"]),
        "追加文件": (_append_file, ["appendfile"]),
        "文件存在": (lambda p: _os.path.exists(ql_str(p)), ["fileexists"]),
        "JSON解析": (lambda s: _json.loads(ql_str(s)), ["jsonparse"]),
        "JSON生成": (lambda x, indent=2: _json.dumps(_jsonable(x), ensure_ascii=False, indent=int(indent)), ["jsonstringify"]),
        # 时间 / 随机
        "现在": (lambda: _time.strftime("%Y-%m-%d %H:%M:%S"), ["now"]),
        "时间戳": (lambda: _time.time(), ["timestamp"]),
        "睡眠": (lambda s: (_time.sleep(_num(s)), None)[1], ["sleep"]),
        "随机": (lambda: _random.random(), ["random"]),
        "随机整数": (lambda a=0, b=None: _random.randint(int(a), int(b)) if b is not None else _random.randint(0, int(a)), ["randint"]),
        # 其他
        "断言": (assert_, ["assert"]),
        "帮助": (help_, ["help"]),
        "退出": (lambda code=0: _sys.exit(int(code)), ["exit"]),
        "格式化": (lambda fmt, *a: _py_format(fmt, a), ["format"]),
        "清屏": (lambda: (_os.system("cls" if _os.name == "nt" else "clear"), None)[1], ["clear"]),
        "参数": (list(interp.argv), ["argv"]),
        "错误": (_make_error, ["error"]),
        "是数字": (lambda x: isinstance(x, (int, float)) and not isinstance(x, bool), ["isnum"]),
        "是字符串": (lambda x: isinstance(x, str), ["isstr"]),
        "是列表": (lambda x: isinstance(x, list), ["islist"]),
        "是字典": (lambda x: isinstance(x, dict), ["isdict"]),
        "是函数": (lambda x: hasattr(x, "fn") or type(x).__name__ == "QlFunction", ["isfn"]),
        "是空": (lambda x: x is None, ["isnil"]),
    }

    global BUILTIN_FN_NAMES
    BUILTIN_FN_NAMES = []
    for name, (fn, aliases) in defs.items():
        BUILTIN_FN_NAMES.append(name)
        if callable(fn) and not isinstance(fn, (list, str)):
            nf = NativeFunction(name, fn)
        else:
            nf = fn
        env.define(name, nf, True)
        for a in aliases:
            env.define(a, nf, True)
    env.define("真", True, True)
    env.define("假", False, True)
    env.define("空", None, True)
    # 系统模块的参数在运行时可变
    sysmod = get_builtin_module("系统")
    sysmod.exports["参数"] = list(interp.argv)


def _make_error(msg="", **kw):
    """错误("消息", 类型="参数错误", 任意附加数据...)"""
    kind = kw.pop("类型", kw.pop("kind", "错误"))
    return QlError(ql_str(kind), ql_str(msg), kw)


def _seq_or_dict(x):
    if isinstance(x, (list, str, dict)):
        return len(x)
    if isinstance(x, QlRange):
        return len(x.to_list())
    raise _err("长度() 需要列表、字符串、字典或区间，实际是 %s" % ql_type(x))


def _range_list(a, b, s):
    a = int(_num(a))
    s = int(_num(s))
    if b is None:
        b, a = a, 0
    else:
        b = int(_num(b))
    if s == 0:
        raise _err("范围() 的步长不能为 0")
    out = []
    i = a
    if s > 0:
        while i < b:
            out.append(i)
            i += s
    else:
        while i > b:
            out.append(i)
            i += s
    return out


def _sort_key(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float, str)):
        return v
    return ql_str(v)


BUILTIN_FN_NAMES = []

BUILTIN_DOCS = {
    "输出": ("向屏幕打印内容，自动换行", "输出(1, \"你好\")"),
    "写": ("打印但不换行", "写(\"请输入：\")"),
    "输入": ("读取一行键盘输入", "让 名字 = 输入(\"你叫什么？\")"),
    "长度": ("返回列表/字符串/字典/区间的长度", "长度([1,2,3])  →  3"),
    "类型": ("返回值的类型名", "类型(1)  →  数字"),
    "范围": ("生成整数列表", "范围(5) → [0,1,2,3,4]；范围(1,10,2) → [1,3,5,7,9]"),
    "映射": ("对列表每个元素执行函数", "映射(x => x*2, [1,2,3]) → [2,4,6]"),
    "过滤": ("保留满足条件的元素", "过滤(x => x>1, [1,2,3]) → [2,3]"),
    "归约": ("把列表归约为一个值", "归约((a,b)=>a+b, [1,2,3]) → 6"),
    "导入": ("导入模块或 .ql 文件", '导入 "数学" 作为 m'),
    "匹配": ("模式匹配", "匹配 x { 情形 1 { ... } 默认 { ... } }"),
}
