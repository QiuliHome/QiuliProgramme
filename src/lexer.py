"""Qiuli 词法分析器

把 .ql 源码切成 token 流。支持中英文双关键字、字符串插值、换行敏感。
"""

from .errors import QiuliError

# ---------------------------------------------------------------- 关键字
# 中文关键字与英文关键字等价，统一归一化为规范名（canonical）
KEYWORDS = {
    # 声明
    "让": "let", "let": "let", "var": "let", "变量": "let",
    "常量": "const", "const": "const", "常": "const",
    "函数": "fn", "fn": "fn", "func": "fn", "function": "fn", "定义": "fn",
    "方法": "method", "method": "method", "静态": "static", "static": "static",
    "类": "class", "class": "class",
    "构造": "init", "init": "init",
    "继承": "extends", "extends": "extends",
    # 控制流
    "如果": "if", "if": "if",
    "又如果": "elif", "否则如果": "elif", "elif": "elif", "elseif": "elif",
    "否则": "else", "else": "else",
    "当": "while", "while": "while",
    "遍历": "for", "for": "for",
    "于": "in", "在": "in", "in": "in",
    "中断": "break", "break": "break",
    "继续": "continue", "continue": "continue",
    "返回": "return", "return": "return",
    "匹配": "match", "match": "match",
    "情形": "case", "case": "case",
    "默认": "default", "default": "default",
    # 字面量
    "真": "true", "true": "true",
    "假": "false", "false": "false",
    "空": "nil", "空值": "nil", "nil": "nil", "null": "nil", "none": "nil",
    # 逻辑
    "且": "and", "and": "and",
    "或": "or", "or": "or",
    "非": "not", "not": "not",
    # 异常
    "尝试": "try", "try": "try",
    "捕获": "catch", "catch": "catch",
    "最终": "finally", "finally": "finally",
    "抛出": "throw", "throw": "throw",
    # 模块
    "导入": "import", "import": "import",
    "作为": "as", "as": "as",
    "从": "from", "from": "from",
    "导出": "export", "export": "export",
    # 面向对象
    "自身": "self", "self": "self", "this": "self",
    "父": "super", "super": "super",
}

# 规范关键字集合（供语法分析快速判断）
RESERVED = set(KEYWORDS.values()) | {"method"}

# 多字符运算符（按长度从长到短匹配）
OPERATORS3 = ("**=", "//=", "..<", "...")
OPERATORS2 = (
    "**", "//", "==", "!=", "<=", ">=", "&&", "||", "=>", "|>", "->",
    "..", "+=", "-=", "*=", "/=", "%=", "??", "?.", "::", "++", "--",
)
OPERATORS1 = "+-*/%=<>!()[]{},.;:?|&^~@"

# 行尾出现这些 token 时，换行不算语句结束（表达式续行）
# 注意：右括号 ) ] } 不能算续行符，否则函数调用后的换行会被吞掉
CONTINUATION = set(OPERATORS1.replace(")", "").replace("]", "").replace("}", "")) | {
    "**", "==", "!=", "<=", ">=", "&&", "||", "=>",
                                  "|>", "->", "..", "..<", "+=", "-=", "*=", "/=",
                                  "%=", "??", "?.", "::", "and", "or", "not",
                                  "in", "as", "extends", "**=", "//="}


class Token:
    __slots__ = ("type", "value", "line", "col")

    def __init__(self, type_, value, line, col):
        self.type = type_      # NUMBER STRING IDENT KEYWORD OP NEWLINE EOF
        self.value = value
        self.line = line
        self.col = col

    def is_op(self, *vals):
        return self.type == "OP" and self.value in vals

    def is_kw(self, *vals):
        return self.type == "KEYWORD" and self.value in vals

    def __repr__(self):
        return "Token(%s, %r, L%d:%d)" % (self.type, self.value, self.line, self.col)


def is_ident_start(ch):
    return ch == "_" or ch.isalpha() or "\u4e00" <= ch <= "\u9fff" or ch in "＄"


def is_ident_part(ch):
    return ch == "_" or ch.isalnum() or "\u4e00" <= ch <= "\u9fff"


ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "0": "\0", "a": "\a", "b": "\b",
    "f": "\f", "v": "\v", "\\": "\\", '"': '"', "'": "'", "$": "$",
    "`": "`", "e": "\x1b",
}


class Lexer:
    def __init__(self, source, filename="<input>"):
        self.src = source
        self.filename = filename
        self.i = 0
        self.line = 1
        self.col = 1
        self.tokens = []
        self.paren = 0          # 圆/方括号 + 字典花括号：深度 > 0 时忽略换行
        self.brace_stack = []   # 记录每个 { 是 "dict" 还是 "block"

    # -------------------------------------------------- 基础移动
    def _peek(self, k=0):
        j = self.i + k
        return self.src[j] if j < len(self.src) else ""

    def _advance(self, n=1):
        for _ in range(n):
            if self.i >= len(self.src):
                return
            if self.src[self.i] == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            self.i += 1

    def _add(self, type_, value, line, col):
        self.tokens.append(Token(type_, value, line, col))

    def error(self, msg, line=None, col=None):
        return QiuliError("词法错误", msg, self.filename,
                          line if line else self.line, col if col else self.col)

    # 花括号前一个 token 属于这些时，认为是「值」（字典/对象字面量）
    DICT_PREV_OPS = {"=", ",", "(", "[", ":", "?", "+", "-", "*", "/", "%",
                     "==", "!=", "<", ">", "<=", ">=", "&&", "||", "|>", "**"}
    DICT_PREV_KW = {"return", "and", "or", "not", "in"}

    def _is_value_brace(self):
        if not self.tokens:
            return False
        p = self.tokens[-1]
        if p.type == "OP":
            return p.value in self.DICT_PREV_OPS
        if p.type == "KEYWORD":
            return p.value in self.DICT_PREV_KW
        return False

    # -------------------------------------------------- 主循环
    def tokenize(self):
        src = self.src
        n = len(src)
        while self.i < n:
            ch = src[self.i]

            # 空白
            if ch in " \t\r":
                self._advance()
                continue

            # 换行
            if ch == "\n":
                line, col = self.line, self.col
                self._advance()
                if self.paren > 0:
                    continue
                if self.tokens:
                    last = self.tokens[-1]
                    if last.type == "NEWLINE":
                        continue
                    if (last.type == "OP" and last.value in CONTINUATION) or \
                       (last.type == "KEYWORD" and last.value in CONTINUATION) or \
                       (last.type == "OP" and last.value in ("(", "[", "{")):
                        continue
                    self._add("NEWLINE", "\n", line, col)
                continue

            # 分号（显式语句结束）
            if ch == ";":
                line, col = self.line, self.col
                self._advance()
                self._add("NEWLINE", ";", line, col)
                continue

            # 注释（注意：// 在 Qiuli 中是整除运算符，单行注释请用 #）
            if ch == "#":
                while self.i < n and src[self.i] != "\n":
                    self._advance()
                continue
            if src.startswith("/*", self.i):
                start_line, start_col = self.line, self.col
                self._advance(2)
                while self.i < n and not src.startswith("*/", self.i):
                    self._advance()
                if self.i >= n:
                    raise self.error("块注释未闭合", start_line, start_col)
                self._advance(2)
                continue

            # 数字
            if ch.isdigit() or (ch == "." and self._peek(1).isdigit()):
                self._read_number()
                continue

            # 字符串
            if ch in "\"'":
                self._read_string()
                continue

            # 标识符 / 关键字
            if is_ident_start(ch):
                self._read_ident()
                continue

            # 运算符
            matched = None
            for cand in OPERATORS3:
                if src.startswith(cand, self.i):
                    matched = cand
                    break
            if not matched:
                for cand in OPERATORS2:
                    if src.startswith(cand, self.i):
                        matched = cand
                        break
            if not matched and ch in OPERATORS1:
                matched = ch

            if matched:
                line, col = self.line, self.col
                self._advance(len(matched))
                if matched == "{":
                    # 区分「字典/表达式」的花括号与「代码块」的花括号：
                    # 代码块的换行是有意义的（分隔语句），字典里的换行要忽略
                    if self._is_value_brace():
                        self.brace_stack.append("dict")
                        self.paren += 1
                    else:
                        self.brace_stack.append("block")
                elif matched == "}":
                    if self.brace_stack and self.brace_stack[-1] == "dict":
                        self.paren -= 1
                        if self.paren < 0:
                            self.paren = 0
                    if self.brace_stack:
                        self.brace_stack.pop()
                elif matched in ("(", "["):
                    self.paren += 1
                elif matched in (")", "]"):
                    self.paren -= 1
                    if self.paren < 0:
                        self.paren = 0
                self._add("OP", matched, line, col)
                continue

            raise self.error("无法识别的字符 %r" % ch)

        # 收尾
        if self.tokens and self.tokens[-1].type == "NEWLINE":
            self.tokens.pop()
        self._add("EOF", None, self.line, self.col)
        return self.tokens

    # -------------------------------------------------- 数字
    def _read_number(self):
        src = self.src
        start = self.i
        line, col = self.line, self.col
        base = 10
        if src.startswith("0x", self.i) or src.startswith("0X", self.i):
            base = 16
            self._advance(2)
        elif src.startswith("0b", self.i) or src.startswith("0B", self.i):
            base = 2
            self._advance(2)
        elif src.startswith("0o", self.i) or src.startswith("0O", self.i):
            base = 8
            self._advance(2)

        isfloat = False
        digits = "0123456789"
        if base == 16:
            digits = "0123456789abcdefABCDEF"
        elif base == 2:
            digits = "01"
        elif base == 8:
            digits = "01234567"

        while self.i < len(src):
            c = src[self.i]
            if c in digits or c == "_":
                self._advance()
            elif c == "." and base == 10 and not isfloat and src[self.i + 1:self.i + 2].isdigit():
                isfloat = True
                self._advance()
            elif c in "eE" and base == 10 and src[self.i - 1] not in "eE":
                # 科学计数法
                j = self.i + 1
                if src[j:j + 1] in "+-":
                    j += 1
                if src[j:j + 1].isdigit():
                    isfloat = True
                    self._advance()
                    if src[self.i:self.i + 1] in "+-":
                        self._advance()
                else:
                    break
            else:
                break

        raw = src[start:self.i].replace("_", "")
        try:
            if base == 10:
                val = float(raw) if isfloat else int(raw)
            else:
                val = int(raw, base)
        except ValueError:
            raise self.error("非法数字字面量 %r" % raw, line, col)

        # 数字后紧跟标识符字符 → 报错
        nxt = src[self.i:self.i + 1]
        if nxt and (nxt.isalnum() or nxt == "_"):
            raise self.error("数字后不能直接跟标识符", line, col)
        self._add("NUMBER", val, line, col)

    # -------------------------------------------------- 字符串
    def _read_string(self):
        src = self.src
        quote = src[self.i]
        line, col = self.line, self.col
        triple = src.startswith(quote * 3, self.i)
        if triple:
            self._advance(3)
        else:
            self._advance()

        buf = []
        while True:
            if self.i >= len(src):
                raise self.error("字符串未闭合", line, col)
            # 插值 ${...}：内部允许出现引号与嵌套的 { }
            if src.startswith("${", self.i):
                buf.append("${")
                self._advance(2)
                depth = 1
                while depth > 0:
                    if self.i >= len(src):
                        raise self.error("字符串插值 ${...} 缺少结尾的 }", line, col)
                    ch = src[self.i]
                    if ch == "\\":
                        buf.append(src[self.i:self.i + 2])
                        self._advance(2)
                        continue
                    if ch in "\"'":                       # 插值里的字符串字面量
                        q = ch
                        buf.append(ch)
                        self._advance()
                        while self.i < len(src) and src[self.i] != q:
                            if src[self.i] == "\\":
                                buf.append(src[self.i:self.i + 2])
                                self._advance(2)
                                continue
                            if src[self.i] == "\n":
                                raise self.error("字符串未闭合", line, col)
                            buf.append(src[self.i])
                            self._advance()
                        if self.i >= len(src):
                            raise self.error("字符串未闭合", line, col)
                        buf.append(src[self.i])
                        self._advance()
                        continue
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            buf.append("}")
                            self._advance()
                            break
                    buf.append(ch)
                    self._advance()
                continue
            c = src[self.i]
            if c == "\\":
                self._advance()
                e = src[self.i:self.i + 1]
                if e == "u":  # \uXXXX
                    self._advance()
                    hexs = src[self.i:self.i + 4]
                    if len(hexs) == 4 and all(x in "0123456789abcdefABCDEF" for x in hexs):
                        buf.append(chr(int(hexs, 16)))
                        self._advance(4)
                        continue
                    raise self.error("非法 \\u 转义", self.line, self.col)
                if e in ESCAPES:
                    buf.append(ESCAPES[e])
                    self._advance()
                    continue
                if e == "":
                    raise self.error("字符串未闭合", line, col)
                raise self.error("非法转义序列 \\%s" % e, self.line, self.col)
            if c == quote:
                if triple:
                    if src.startswith(quote * 3, self.i):
                        self._advance(3)
                        break
                    buf.append(c)
                    self._advance()
                    continue
                self._advance()
                break
            if c == "\n" and not triple:
                raise self.error("字符串未闭合（单行字符串不能换行）", line, col)
            buf.append(c)
            self._advance()

        self._add("STRING", "".join(buf), line, col)

    # -------------------------------------------------- 标识符
    def _read_ident(self):
        src = self.src
        start = self.i
        line, col = self.line, self.col
        while self.i < len(src) and is_ident_part(src[self.i]):
            self._advance()
        raw = src[start:self.i]
        canon = KEYWORDS.get(raw)
        if canon:
            self._add("KEYWORD", canon, line, col)
        else:
            self._add("IDENT", raw, line, col)


def tokenize(source, filename="<input>"):
    return Lexer(source, filename).tokenize()
