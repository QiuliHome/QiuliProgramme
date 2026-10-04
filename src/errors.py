"""Qiuli 错误体系：编译期错误与运行期错误，均带源码定位与高亮展示。"""


def _visible_len(s):
    """按显示宽度计算长度（中日韩全角字符算 2 列）"""
    w = 0
    for ch in s:
        o = ord(ch)
        if (0x1100 <= o <= 0x115F) or (0x2E80 <= o <= 0xA4CF) or \
           (0xAC00 <= o <= 0xD7A3) or (0xF900 <= o <= 0xFAFF) or \
           (0xFE30 <= o <= 0xFE6F) or (0xFF00 <= o <= 0xFF60) or \
           (0xFFE0 <= o <= 0xFFE6) or (0x20000 <= o <= 0x3FFFD):
            w += 2
        else:
            w += 1
    return w


class QiuliError(Exception):
    """编译期 / 语法错误"""

    def __init__(self, kind, msg, filename="<input>", line=0, col=0,
                 source=None, hint=None):
        super().__init__(msg)
        self.kind = kind
        self.msg = msg
        self.filename = filename
        self.line = line
        self.col = col
        self.source = source
        self.hint = hint

    def render(self, color=True):
        G = "\033[91m" if color else ""
        D = "\033[90m" if color else ""
        Y = "\033[93m" if color else ""
        R = "\033[0m" if color else ""
        out = []
        out.append("%s%s: %s%s" % (G, self.kind, self.msg, R))
        out.append("%s  ── %s:%d:%d%s" % (D, self.filename, self.line, self.col, R))
        if self.source and self.line:
            lines = self.source.split("\n")
            idx = self.line - 1
            if 0 <= idx < len(lines):
                text = lines[idx]
                out.append("%s%d | %s%s" % (D, self.line, R + text, ""))
                pad = _visible_len(text[: max(self.col - 1, 0)])
                out.append("%s  | %s^%s" % (D, " " * pad, R))
        if self.hint:
            out.append("%s提示：%s%s" % (Y, self.hint, R))
        return "\n".join(out)

    def __str__(self):
        return self.render(color=False)


class QiuliRuntimeError(Exception):
    """运行期错误"""

    def __init__(self, msg, filename="<input>", line=0, source=None,
                 stack=None, hint=None):
        super().__init__(msg)
        self.msg = msg
        self.filename = filename
        self.line = line
        self.source = source
        self.stack = stack or []   # [(filename, line, name), ...]
        self.hint = hint

    def render(self, color=True):
        G = "\033[91m" if color else ""
        D = "\033[90m" if color else ""
        Y = "\033[93m" if color else ""
        R = "\033[0m" if color else ""
        out = ["%s运行错误: %s%s" % (G, self.msg, R)]
        if self.stack:
            out.append("%s回溯（最近调用最后）:%s" % (D, R))
            for fn, ln, name in self.stack[-12:]:
                where = "%s:%s" % (fn, ln)
                out.append("%s    at %s%s%s" % (D, name, " (%s)" % where if where else "", R))
        elif self.line:
            out.append("%s  ── %s:%d%s" % (D, self.filename, self.line, R))
        if self.source and self.line:
            lines = self.source.split("\n")
            idx = self.line - 1
            if 0 <= idx < len(lines):
                out.append("%s%d | %s%s" % (D, self.line, R, lines[idx]))
        if self.hint:
            out.append("%s提示：%s%s" % (Y, self.hint, R))
        return "\n".join(out)

    def __str__(self):
        return self.render(color=False)


class QiuliThrow(Exception):
    """Qiuli 代码里 抛出/throw 出来的值，由 尝试/try 捕获"""

    def __init__(self, value):
        super().__init__(str(value))
        self.value = value


class ReturnSignal(Exception):
    """函数返回的内部信号"""

    def __init__(self, value):
        self.value = value


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass
