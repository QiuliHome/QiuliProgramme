"""Qiuli 运行时对象：函数、类、实例、模块、错误。"""

NIL = None


class QlFunction:
    """用户定义的函数 / 方法 / lambda"""

    __slots__ = ("name", "params", "body", "expr_body", "closure",
                 "is_method", "filename", "line", "exported")

    def __init__(self, name, params, body, closure, expr_body=False,
                 is_method=False, filename="<input>", line=0):
        self.name = name or "<匿名>"
        self.params = params          # list[Param]
        self.body = body
        self.expr_body = expr_body
        self.closure = closure
        self.is_method = is_method
        self.filename = filename
        self.line = line
        self.exported = False

    def __repr__(self):
        return "<函数 %s>" % self.name


class NativeFunction:
    """宿主（Python）实现的函数"""

    __slots__ = ("name", "fn", "arity", "doc")

    def __init__(self, name, fn, arity=-1, doc=""):
        self.name = name
        self.fn = fn
        self.arity = arity
        self.doc = doc

    def __repr__(self):
        return "<内置函数 %s>" % self.name


class QlClass:
    __slots__ = ("name", "methods", "superclass", "fields", "filename", "exported")

    def __init__(self, name, methods=None, superclass=None, fields=None,
                 filename="<input>"):
        self.name = name
        self.methods = methods or {}
        self.superclass = superclass
        self.fields = fields or {}
        self.filename = filename
        self.exported = False

    def find_method(self, name):
        c = self
        while c is not None:
            if name in c.methods:
                return c.methods[name]
            c = c.superclass
        return None

    def __repr__(self):
        return "<类 %s>" % self.name


class QlInstance:
    __slots__ = ("cls", "fields")

    def __init__(self, cls):
        self.cls = cls
        self.fields = {}

    def get(self, name):
        if name in self.fields:
            return self.fields[name]
        m = self.cls.find_method(name)
        if m is not None:
            return BoundMethod(self, m)
        return None

    def has(self, name):
        return name in self.fields or self.cls.find_method(name) is not None

    def __repr__(self):
        return "<%s 对象>" % self.cls.name


class BoundMethod:
    __slots__ = ("receiver", "func", "name")

    def __init__(self, receiver, func):
        self.receiver = receiver
        self.func = func
        self.name = func.name

    def __repr__(self):
        return "<方法 %s.%s>" % (self.receiver.cls.name, self.func.name)


class BuiltinMethod:
    """内置类型上的方法，如 "abc".大写()"""

    __slots__ = ("obj", "name", "fn", "doc")

    def __init__(self, obj, name, fn, doc=""):
        self.obj = obj
        self.name = name
        self.fn = fn
        self.doc = doc

    def __repr__(self):
        return "<内置方法 %s.%s>" % (ql_type(self.obj), self.name)


class QlRange:
    """区间 1..10 的惰性表示"""

    __slots__ = ("start", "end", "step", "inclusive")

    def __init__(self, start, end, step=1, inclusive=True):
        self.start = start
        self.end = end
        self.step = step
        self.inclusive = inclusive

    def to_list(self):
        if self.step == 0:
            return []
        end = self.end + 1 if self.inclusive else self.end
        if self.step > 0:
            out = []
            i = self.start
            while i < end:
                out.append(i)
                i += self.step
            return out
        out = []
        i = self.start
        while i > end:
            out.append(i)
            i += self.step
        return out

    def __len__(self):
        return len(self.to_list())

    def __repr__(self):
        return "区间(%s..%s)" % (self.start, self.end)


class QlModule:
    __slots__ = ("name", "exports", "filename")

    def __init__(self, name, exports=None, filename="<module>"):
        self.name = name
        self.exports = exports or {}
        self.filename = filename

    def __repr__(self):
        return "<模块 %s>" % self.name


class QlError:
    """Qiuli 中的错误对象，可被 抛出 / 捕获"""

    __slots__ = ("kind", "message", "data")

    def __init__(self, kind="错误", message="", data=None):
        self.kind = kind
        self.message = message
        self.data = data if data is not None else {}

    def __repr__(self):
        return "%s: %s" % (self.kind, self.message) if self.message else self.kind


# ------------------------------------------------------------------ 工具
def truthy(v):
    """只有 空(nil) 与 假(false) 为假，0 与 "" 为真"""
    return not (v is None or v is False)


def ql_type(v):
    if v is None:
        return "空值"
    if isinstance(v, bool):
        return "布尔"
    if isinstance(v, (int, float)):
        return "数字"
    if isinstance(v, str):
        return "字符串"
    if isinstance(v, list):
        return "列表"
    if isinstance(v, dict):
        return "字典"
    if isinstance(v, QlFunction):
        return "函数"
    if isinstance(v, NativeFunction):
        return "内置函数"
    if isinstance(v, QlClass):
        return "类"
    if isinstance(v, QlInstance):
        return "对象"
    if isinstance(v, BoundMethod):
        return "方法"
    if isinstance(v, QlModule):
        return "模块"
    if isinstance(v, QlError):
        return "错误"
    return type(v).__name__


def ql_str(v, seen=None):
    """Qiuli 值 → 显示字符串（不含外层引号）"""
    seen = seen or set()
    if v is None:
        return "空"
    if v is True:
        return "真"
    if v is False:
        return "假"
    if isinstance(v, str):
        return v
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return repr(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        if id(v) in seen:
            return "[...]"
        seen.add(id(v))
        out = "[" + ", ".join(ql_repr(x, seen) for x in v) + "]"
        seen.discard(id(v))
        return out
    if isinstance(v, dict):
        if id(v) in seen:
            return "{...}"
        seen.add(id(v))
        out = "{" + ", ".join("%s: %s" % (ql_repr(k, seen), ql_repr(x, seen))
                              for k, x in v.items()) + "}"
        seen.discard(id(v))
        return out
    if isinstance(v, QlInstance):
        return "<%s 对象>" % v.cls.name
    return repr(v)


def ql_repr(v, seen=None):
    """REPL 显示：字符串带引号"""
    if isinstance(v, str):
        return '"%s"' % v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return ql_str(v, seen)
