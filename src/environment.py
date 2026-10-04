"""Qiuli 作用域环境：链式查找 + 常量保护。"""

from .errors import QiuliRuntimeError

UNDEFINED = object()


class Environment:
    __slots__ = ("vars", "consts", "parent", "name")

    def __init__(self, parent=None, name="全局"):
        self.vars = {}
        self.consts = set()
        self.parent = parent
        self.name = name

    def define(self, name, value, const=False, line=0, source=None, filename="<input>"):
        self.vars[name] = value
        if const:
            self.consts.add(name)

    def lookup_env(self, name):
        e = self
        while e is not None:
            if name in e.vars:
                return e
            e = e.parent
        return None

    def get(self, name):
        e = self.lookup_env(name)
        if e is None:
            return UNDEFINED
        return e.vars[name]

    def set(self, name, value, line=0, filename="<input>", source=None):
        e = self.lookup_env(name)
        if e is None:
            raise QiuliRuntimeError(
                "未定义的变量 %r" % name, filename, line, source,
                hint="先使用 让 %s = ... 声明它" % name)
        if name in e.consts:
            raise QiuliRuntimeError(
                "不能给常量 %r 重新赋值" % name, filename, line, source,
                hint="常量用 常量 声明，如需修改请改用 让")
        e.vars[name] = value

    def set_here(self, name, value, const=False):
        self.vars[name] = value
        if const:
            self.consts.add(name)

    def snapshot(self):
        out = {}
        e = self
        while e is not None:
            for k, v in e.vars.items():
                out.setdefault(k, v)
            e = e.parent
        return out

    def __repr__(self):
        return "<环境 %s: %d 个绑定>" % (self.name, len(self.vars))
