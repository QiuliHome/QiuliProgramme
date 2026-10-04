"""Qiuli 解释器：树遍历执行。"""

import os
import sys

sys.setrecursionlimit(20000)

from . import ast_nodes as A
from . import builtins as B
from .environment import Environment, UNDEFINED
from .errors import (QiuliError, QiuliRuntimeError, QiuliThrow, ReturnSignal,
                     BreakSignal, ContinueSignal)
from .objects import (QlFunction, NativeFunction, QlClass, QlInstance,
                      BoundMethod, BuiltinMethod, QlModule, QlError, QlRange,
                      truthy, ql_type, ql_str, ql_repr)
from .parser import parse

OP_METHODS = {
    "+": "__加__", "-": "__减__", "*": "__乘__", "/": "__除__",
    "%": "__取余__", "**": "__幂__", "==": "__等于__", "<": "__小于__",
    "<=": "__小于等于__", ">": "__大于__", ">=": "__大于等于__",
}


class Interpreter:
    def __init__(self, base_dir=None, stdout=None, stderr=None, argv=None):
        self.base_dir = base_dir or os.getcwd()
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr
        self.argv = argv or []
        self.filename = "<输入>"
        self.source = ""
        self.call_stack = []           # [(函数名, 文件名, 行号)]
        self.modules = {}              # 绝对路径 -> QlModule
        self.builtin_env = Environment(None, "内置")
        self.global_env = Environment(self.builtin_env, "全局")
        B.register_builtins(self.builtin_env, self)
        self.depth = 0
        self.max_depth = 800
        self._func_def_cache = {}

    # ------------------------------------------------------------ 错误
    def error(self, msg, line=0, hint=None):
        return QiuliRuntimeError(msg, self.filename, line, self.source,
                                 list(self.call_stack), hint)

    def type_error(self, op, a, b=None, line=0):
        if b is None:
            return self.error("类型错误：%s 不支持 %s 类型的值" % (op, ql_type(a)),
                              line, hint="检查变量的实际类型，可用 类型(x) 查看")
        return self.error("类型错误：不能用 %s 对 %s 和 %s 运算" % (op, ql_type(a), ql_type(b)),
                          line, hint="可用 字符串(x) / 数字(x) 显式转换")

    # ------------------------------------------------------------ 入口
    def run_source(self, source, filename="<输入>", env=None):
        prog = parse(source, filename)
        self.filename = filename
        self.source = source
        return self.visit(prog, env or self.global_env)

    def run_file(self, path, argv=None):
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise QiuliRuntimeError("找不到文件：%s" % path, "<命令行>", 0)
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        self.base_dir = os.path.dirname(path)
        self.argv = argv if argv is not None else self.argv
        return self.run_source(source, path, self.global_env)

    # ------------------------------------------------------------ 分发
    def visit(self, node, env):
        return self._visit(node, env)

    def _visit(self, node, env):
        t = type(node)

        # ---------------- 语句 ----------------
        if t is A.Program:
            for s in node.body:
                self.visit(s, env)
            return None

        if t is A.Block:
            inner = Environment(env, "块")
            for s in node.body:
                self.visit(s, inner)
            return None

        if t is A.VarDecl:
            val = self.visit(node.init, env) if node.init is not None else None
            env.define(node.name, val, node.const)
            return val

        if t is A.ExprStmt:
            return self.visit(node.expr, env)

        if t is A.IfStmt:
            if truthy(self.visit(node.cond, env)):
                return self.visit(node.then_block, env)
            for c, blk in node.elifs:
                if truthy(self.visit(c, env)):
                    return self.visit(blk, env)
            if node.else_block is not None:
                return self.visit(node.else_block, env)
            return None

        if t is A.WhileStmt:
            n = 0
            reuse = not self.has_func_def(node.body)
            while truthy(self.visit(node.cond, env)):
                n += 1
                if n > 50_000_000:
                    raise self.error("循环次数过多，疑似死循环", node.line)
                try:
                    if reuse:
                        for st in node.body.body:
                            self.visit(st, env)
                    else:
                        self.visit(node.body, env)
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue
            return None

        if t is A.ForStmt:
            it = self.visit(node.iterable, env)
            items = None
            if isinstance(it, dict):
                items = list(it.items())
            else:
                items = self.iter_items(it, node.line)
            two = node.index_var is not None
            if two:
                loop_iter = list(enumerate(items))
                # 字典直接给出 (键, 值)，其它类型给出 (下标, 元素)
                if isinstance(it, dict):
                    loop_iter = items
            else:
                loop_iter = items
            # 循环体里没有函数/类定义时，复用同一个环境（省掉每轮新建作用域的开销）
            reuse = not self.has_func_def(node.body)
            idx = 0
            for item in loop_iter:
                inner = env if reuse else Environment(env, "循环")
                if two:
                    inner.define(node.index_var, item[0])
                    inner.define(node.var, item[1])
                else:
                    if node.index_var:
                        inner.define(node.index_var, idx)
                    inner.define(node.var, item)
                idx += 1
                try:
                    if reuse:
                        for st in node.body.body:
                            self.visit(st, inner)
                    else:
                        self.visit(node.body, inner)
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue
            return None

        if t is A.BreakStmt:
            raise BreakSignal()
        if t is A.ContinueStmt:
            raise ContinueSignal()

        if t is A.ReturnStmt:
            raise ReturnSignal(self.visit(node.value, env) if node.value is not None else None)

        if t is A.ThrowStmt:
            v = self.visit(node.value, env)
            raise QiuliThrow(v if isinstance(v, QlError) else v)

        if t is A.FnDecl:
            fn = QlFunction(node.name, node.params, node.body, env,
                            node.expr_body, node.is_method,
                            self.filename, node.line)
            env.define(node.name, fn)
            fn.exported = node.exported
            return fn

        if t is A.Lambda:
            return QlFunction("<匿名>", node.params, node.body, env,
                              node.expr_body, False, self.filename, node.line)

        if t is A.ClassDecl:
            sup = None
            if node.superclass is not None:
                sup = self.visit(node.superclass, env)
                if not isinstance(sup, QlClass):
                    raise self.error("继承的目标必须是类，实际是 %s" % ql_type(sup), node.line)
            methods = {}
            for m in node.methods:
                methods[m.name] = QlFunction(m.name, m.params, m.body, env,
                                             m.expr_body, True, self.filename, m.line)
            cls = QlClass(node.name, methods, sup, filename=self.filename)
            # 类字段（在定义时求值一次，实例化时复制到实例）
            fields = {}
            for f in node.fields:
                if isinstance(f, A.VarDecl):
                    fields[f.name] = self.visit(f.init, env) if f.init is not None else None
                else:
                    fields[f.name] = None
            cls.fields = fields
            cls.exported = node.exported
            env.define(node.name, cls)
            return cls

        if t is A.TryStmt:
            try:
                try:
                    self.visit(node.body, env)
                except (ReturnSignal, BreakSignal, ContinueSignal):
                    raise                      # 控制流信号不能被捕获
                except QiuliThrow as e:
                    val = e.value
                    kind = val.kind if isinstance(val, QlError) else ql_type(val)
                    if not self._handle_catch(node, kind, val, env):
                        raise
                except QiuliRuntimeError as e:
                    if not self._handle_catch(node, "运行错误",
                                              QlError("运行错误", e.msg), env):
                        raise
                except Exception as e:           # 宿主异常（文件权限等）也转成错误
                    if not self._handle_catch(
                            node, "系统错误",
                            QlError("系统错误", "%s: %s" % (type(e).__name__, e)), env):
                        raise
            finally:
                if node.finally_block is not None:
                    self.visit(node.finally_block, env)
            return None

        if t is A.MatchStmt:
            subj = self.visit(node.subject, env)
            for pat, blk in node.cases:
                inner = Environment(env, "情形")
                if self.match_pattern(pat, subj, inner):
                    return self.visit(blk, inner)
            if node.default is not None:
                return self.visit(node.default, env)
            return None

        if t is A.ImportStmt:
            return self.do_import(node, env)

        if t is A.ExportStmt:
            return None

        if t is A.Assign:
            return self.do_assign(node, env)

        # ---------------- 表达式 ----------------
        if t is A.Literal:
            return node.value

        if t is A.InterpString:
            out = []
            for p in node.parts:
                if isinstance(p, A.Literal):
                    out.append(ql_str(p.value))
                else:
                    out.append(ql_str(self.visit(p, env)))
            return "".join(out)

        if t is A.Ident:
            v = env.get(node.name)
            if v is UNDEFINED:
                raise self.error("未定义的变量 %r" % node.name, node.line,
                                 hint="可用 让 %s = ... 声明，或检查拼写" % node.name)
            return v

        if t is A.SelfExpr:
            v = env.get("self")
            if v is UNDEFINED:
                raise self.error("self 只能在类的方法内部使用", node.line)
            return v

        if t is A.SuperExpr:
            self_obj = env.get("self")
            if self_obj is UNDEFINED or not isinstance(self_obj, QlInstance):
                raise self.error("父 只能在类的方法内部使用", node.line)
            sup = self_obj.cls.superclass
            if sup is None:
                raise self.error("类 %s 没有父类" % self_obj.cls.name, node.line)
            if node.method is None:
                return sup
            m = sup.find_method(node.method)
            if m is None:
                raise self.error("父类 %s 中没有方法 %r" % (sup.name, node.method), node.line)
            return BoundMethod(self_obj, m)

        if t is A.ListExpr:
            return [self.visit(x, env) for x in node.items]

        if t is A.DictExpr:
            d = {}
            for k, v in zip(node.keys, node.values):
                d[self.visit(k, env)] = self.visit(v, env)
            return d

        if t is A.Binary:
            return self.do_binary(node, env)

        if t is A.Unary:
            return self.do_unary(node, env)

        if t is A.Logical:
            lv = self.visit(node.left, env)
            if node.op == "and":
                return self.visit(node.right, env) if truthy(lv) else lv
            return lv if truthy(lv) else self.visit(node.right, env)

        if t is A.Ternary:
            return self.visit(node.a, env) if truthy(self.visit(node.cond, env)) \
                else self.visit(node.b, env)

        if t is A.Range:
            s = self.visit(node.start, env)
            e = self.visit(node.end, env)
            return QlRange(s, e, 1, node.inclusive)

        if t is A.Index:
            obj = self.visit(node.obj, env)
            key = self.visit(node.key, env)
            return self.get_index(obj, key, node.line)

        if t is A.Slice:
            obj = self.visit(node.obj, env)
            start = self.visit(node.start, env) if node.start is not None else None
            end = self.visit(node.end, env) if node.end is not None else None
            if isinstance(obj, (list, str)):
                return obj[start:end]
            raise self.type_error("切片", obj, line=node.line)

        if t is A.Member:
            obj = self.visit(node.obj, env)
            if obj is None and node.safe:
                return None
            return self.get_member(obj, node.name, node.line, safe=node.safe)

        if t is A.Call:
            callee = self.visit(node.callee, env)
            args = [self.visit(a, env) for a in node.args]
            named = {k: self.visit(v, env) for k, v in node.named.items()}
            return self.call_value(callee, args, named, node.line, env)

        if t is A.Pattern:
            return None

        raise self.error("解释器未实现的节点：%s" % t.__name__, getattr(node, "line", 0))

    # ------------------------------------------------------------ 静态分析
    def has_func_def(self, node):
        """子树里是否出现函数/lambda/类定义（决定是否必须新建作用域）"""
        key = id(node)
        cached = self._func_def_cache.get(key)
        if cached is not None:
            return cached
        found = False
        stack = [node]
        while stack:
            n = stack.pop()
            if isinstance(n, (A.FnDecl, A.Lambda, A.ClassDecl)):
                found = True
                break
            for _, ch in n.children():
                stack.append(ch)
        self._func_def_cache[key] = found
        return found

    # ------------------------------------------------------------ 赋值
    def do_assign(self, node, env):
        val = self.visit(node.value, env)
        tgt = node.target
        if node.op != "=":
            cur = self.read_target(tgt, env, node.line)
            val = self.binary_op(node.op[:-1], cur, val, node.line)
        if isinstance(tgt, A.Ident):
            env.set(tgt.name, val, node.line, self.filename, self.source)
        elif isinstance(tgt, A.Member):
            obj = self.visit(tgt.obj, env)
            self.set_member(obj, tgt.name, val, node.line)
        elif isinstance(tgt, A.Index):
            obj = self.visit(tgt.obj, env)
            key = self.visit(tgt.key, env)
            self.set_index(obj, key, val, node.line)
        else:
            raise self.error("不能给这个东西赋值", node.line)
        return val

    def read_target(self, tgt, env, line):
        if isinstance(tgt, A.Ident):
            v = env.get(tgt.name)
            if v is UNDEFINED:
                raise self.error("未定义的变量 %r" % tgt.name, line)
            return v
        if isinstance(tgt, A.Member):
            return self.get_member(self.visit(tgt.obj, env), tgt.name, line)
        if isinstance(tgt, A.Index):
            return self.get_index(self.visit(tgt.obj, env), self.visit(tgt.key, env), line)
        raise self.error("无效的赋值目标", line)

    # ------------------------------------------------------------ 下标
    def get_index(self, obj, key, line):
        if isinstance(obj, list):
            if isinstance(key, QlRange):
                return obj[key.to_list()] if False else [obj[i] for i in key.to_list()
                                                         if -len(obj) <= i < len(obj)]
            if not isinstance(key, int):
                raise self.error("列表下标必须是整数，实际是 %s" % ql_type(key), line)
            if key < 0:
                key += len(obj)
            if not (0 <= key < len(obj)):
                raise self.error("下标越界：下标 %d，列表长度 %d" % (key, len(obj)), line)
            return obj[key]
        if isinstance(obj, str):
            if not isinstance(key, int):
                raise self.error("字符串下标必须是整数，实际是 %s" % ql_type(key), line)
            if key < 0:
                key += len(obj)
            if not (0 <= key < len(obj)):
                raise self.error("下标越界：下标 %d，字符串长度 %d" % (key, len(obj)), line)
            return obj[key]
        if isinstance(obj, dict):
            return obj.get(key)          # 缺失返回 空
        if isinstance(obj, QlInstance):
            m = obj.cls.find_method("__下标__")
            if m:
                return self.call_value(BoundMethod(obj, m), [key], {}, line, None)
        raise self.type_error("下标访问", obj, line=line)

    def set_index(self, obj, key, val, line):
        if isinstance(obj, list):
            if not isinstance(key, int):
                raise self.error("列表下标必须是整数", line)
            if key < 0:
                key += len(obj)
            if not (0 <= key < len(obj)):
                raise self.error("下标越界：下标 %d，列表长度 %d" % (key, len(obj)), line)
            obj[key] = val
            return
        if isinstance(obj, dict):
            obj[key] = val
            return
        raise self.type_error("下标赋值", obj, line=line)

    # ------------------------------------------------------------ 成员
    def get_member(self, obj, name, line, safe=False):
        if obj is None:
            if safe:
                return None
            raise self.error("空值 没有成员 %r" % name, line,
                             hint="可用 ?. 安全访问：x?.%s" % name)
        if isinstance(obj, QlInstance):
            if name in obj.fields:
                return obj.fields[name]
            m = obj.cls.find_method(name)
            if m is not None:
                return BoundMethod(obj, m)
            raise self.error("对象 %s 没有属性 %r" % (obj.cls.name, name), line)
        if isinstance(obj, QlClass):
            if name in obj.methods:
                return obj.methods[name]
            if name in obj.fields:
                return obj.fields[name]
            raise self.error("类 %s 没有静态成员 %r" % (obj.name, name), line)
        if isinstance(obj, QlModule):
            if name in obj.exports:
                return obj.exports[name]
            raise self.error("模块 %s 没有导出 %r" % (obj.name, name), line)
        if isinstance(obj, QlError):
            table = {"消息": obj.message, "message": obj.message,
                     "类型": obj.kind, "kind": obj.kind,
                     "数据": obj.data, "data": obj.data}
            if name in table:
                return table[name]
            raise self.error("错误对象没有成员 %r" % name, line)
        m = B.get_member(obj, name)
        if m is not None:
            return m
        if isinstance(obj, (int, float)):
            raise self.error("数字没有成员 %r" % name, line)
        raise self.error("%s 类型没有成员 %r" % (ql_type(obj), name), line)

    def set_member(self, obj, name, val, line):
        if isinstance(obj, QlInstance):
            obj.fields[name] = val
            return
        if isinstance(obj, dict):
            obj[name] = val
            return
        if isinstance(obj, QlModule):
            raise self.error("不能修改模块 %s 的导出" % obj.name, line)
        raise self.type_error("属性赋值 .%s" % name, obj, line=line)

    # ------------------------------------------------------------ 运算
    def do_unary(self, node, env):
        v = self.visit(node.right, env)
        op = node.op
        if op == "-":
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return -v
            if isinstance(v, QlInstance):
                m = v.cls.find_method("__负__")
                if m:
                    return self.call_value(BoundMethod(v, m), [], {}, node.line, env)
            raise self.type_error("一元 -", v, line=node.line)
        if op == "+":
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return +v
            raise self.type_error("一元 +", v, line=node.line)
        if op == "not":
            return not truthy(v)
        if op == "~":
            if isinstance(v, int):
                return ~v
            raise self.type_error("按位取反 ~", v, line=node.line)
        raise self.error("未知的运算符 %r" % op, node.line)

    def do_binary(self, node, env):
        op = node.op
        if op == "//":
            a = self.visit(node.left, env)
            b = self.visit(node.right, env)
            if isinstance(a, int) and isinstance(b, int):
                if b == 0:
                    raise self.error("除数不能为 0", node.line)
                return a // b
            raise self.type_error("//", a, b, node.line)
        if op == "%":
            a = self.visit(node.left, env)
            b = self.visit(node.right, env)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if b == 0:
                    raise self.error("取余的除数不能为 0", node.line)
                return a % b
            if isinstance(a, str):
                try:
                    return a % b if not isinstance(b, (list, dict)) else a % tuple(b)
                except Exception:
                    raise self.type_error("%", a, b, node.line)
            raise self.type_error("%", a, b, node.line)
        a = self.visit(node.left, env)
        b = self.visit(node.right, env)
        return self.binary_op(op, a, b, node.line)

    def binary_op(self, op, a, b, line):
        if op == "==":
            if isinstance(a, QlInstance):
                m = a.cls.find_method("__等于__")
                if m:
                    return truthy(self.call_value(BoundMethod(a, m), [b], {}, line, None))
            return self.deep_eq(a, b)
        if op == "!=":
            return not self.binary_op("==", a, b, line)

        # 字符串拼接（自动转换另一侧）
        if op == "+":
            if isinstance(a, str):
                return a + ql_str(b)
            if isinstance(b, str):
                return ql_str(a) + b
            if isinstance(a, list) and isinstance(b, list):
                return a + b
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
                    and not isinstance(a, bool) and not isinstance(b, bool):
                return a + b
            if isinstance(a, QlInstance):
                m = a.cls.find_method(OP_METHODS["+"])
                if m:
                    return self.call_value(BoundMethod(a, m), [b], {}, line, None)
            raise self.type_error("+", a, b, line)

        # 重复：字符串 × 数字、列表 × 数字
        if op == "*":
            if isinstance(a, str) and isinstance(b, int) and not isinstance(b, bool):
                return a * b
            if isinstance(b, str) and isinstance(a, int) and not isinstance(a, bool):
                return b * a
            if isinstance(a, list) and isinstance(b, int) and not isinstance(b, bool):
                return a * b
            if isinstance(b, list) and isinstance(a, int) and not isinstance(a, bool):
                return b * a

        if isinstance(a, QlInstance):
            m = a.cls.find_method(OP_METHODS.get(op, ""))
            if m:
                return self.call_value(BoundMethod(a, m), [b], {}, line, None)

        if op in ("-", "*", "/", "**"):
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
                    and not isinstance(a, bool) and not isinstance(b, bool):
                if op == "-":
                    return a - b
                if op == "*":
                    if isinstance(a, str) or isinstance(b, str):
                        if isinstance(a, str) and isinstance(b, int):
                            return a * b
                        if isinstance(b, str) and isinstance(a, int):
                            return b * a
                    return a * b
                if op == "/":
                    if b == 0:
                        raise self.error("除数不能为 0", line)
                    r = a / b
                    if isinstance(a, int) and isinstance(b, int) and a % b == 0:
                        return int(r)
                    return r
                if op == "**":
                    try:
                        return a ** b
                    except OverflowError:
                        raise self.error("幂运算结果过大", line)
            raise self.type_error(op, a, b, line)

        if op in ("<", "<=", ">", ">="):
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
                    and not isinstance(a, bool) and not isinstance(b, bool):
                pass
            elif isinstance(a, str) and isinstance(b, str):
                pass
            else:
                raise self.type_error(op, a, b, line)
            if op == "<":
                return a < b
            if op == "<=":
                return a <= b
            if op == ">":
                return a > b
            return a >= b

        if op == "//":
            pass
        raise self.error("未知的运算符 %r" % op, line)

    def deep_eq(self, a, b):
        if isinstance(a, bool) != isinstance(b, bool):
            return False
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                return False
            return all(self.deep_eq(x, y) for x, y in zip(a, b))
        if isinstance(a, dict) and isinstance(b, dict):
            if len(a) != len(b):
                return False
            for k, v in a.items():
                if k not in b:
                    return False
                if not self.deep_eq(v, b[k]):
                    return False
            return True
        try:
            return bool(a == b)
        except Exception:
            return False

    # ------------------------------------------------------------ 调用
    def call_value(self, callee, args, named, line, env=None):
        if isinstance(callee, QlFunction):
            return self.call_function(callee, args, named, None, line)
        if isinstance(callee, BoundMethod):
            return self.call_function(callee.func, args, named, callee.receiver, line)
        if isinstance(callee, NativeFunction):
            self.call_stack.append((callee.name, self.filename, line))
            try:
                return callee.fn(*args, **named) if named else callee.fn(*args)
            except TypeError as e:
                raise self.error("调用 %s 时参数不匹配：%s" % (callee.name, e), line)
            except QiuliRuntimeError as e:
                # 内置函数抛出的错误补上调用位置，方便定位（如 断言 失败）
                if not e.line:
                    e.line = line
                if not e.stack:
                    e.stack = list(self.call_stack)
                raise
            finally:
                self.call_stack.pop()
        if isinstance(callee, BuiltinMethod):
            try:
                return callee.fn(callee.obj, *args)
            except QiuliRuntimeError:
                raise
            except TypeError as e:
                raise self.error("调用 %s() 时参数不匹配：%s" % (callee.name, e), line)
            except Exception as e:
                raise self.error("调用 %s() 失败：%s" % (callee.name, e), line)
        if isinstance(callee, QlClass):
            return self.instantiate(callee, args, named, line)
        if isinstance(callee, QlInstance):
            m = callee.cls.find_method("__调用__")
            if m:
                return self.call_value(BoundMethod(callee, m), args, named, line, env)
        if isinstance(callee, QlModule):
            raise self.error("模块 %s 不能当作函数调用" % callee.name, line)
        raise self.type_error("调用", callee, line=line)

    def call_function(self, func, args, named, receiver, line):
        env = Environment(func.closure, func.name)
        named = dict(named)
        if receiver is not None:
            env.define("self", receiver, True)
        i = 0
        for p in func.params:
            if p.vararg:
                env.define(p.name, list(args[i:]))
                i = len(args)
                continue
            if i < len(args):
                env.define(p.name, args[i])
                i += 1
            elif p.name in named:
                env.define(p.name, named.pop(p.name))
            elif p.default is not None:
                env.define(p.name, self.visit(p.default, env))
            else:
                raise self.error("调用函数 %s 时缺少参数 %r" % (func.name, p.name), line)
        if i < len(args):
            raise self.error("调用函数 %s 时参数过多：期望 %d 个，得到 %d 个"
                             % (func.name, len(func.params), len(args)), line)
        for k, v in named.items():
            env.define(k, v)

        self.depth += 1
        if self.depth > self.max_depth:
            self.depth = 0
            raise self.error("递归过深（超过 %d 层），可能是无限递归" % self.max_depth, line)
        self.call_stack.append((func.name, self.filename, line))
        try:
            if func.expr_body:
                return self.visit(func.body, env)
            self.visit(func.body, env)
            return None
        except ReturnSignal as r:
            return r.value
        except RecursionError:
            self.depth = 0
            raise self.error("递归层数超过 Python 限制，请检查是否存在无限递归", line)
        finally:
            self.depth -= 1
            self.call_stack.pop()

    def instantiate(self, cls, args, named, line):
        obj = QlInstance(cls)
        for k, v in (cls.fields or {}).items():
            obj.fields[k] = v
        init = cls.find_method("init")
        if init is not None:
            self.call_function(init, args, named, obj, line)
        elif args:
            raise self.error("类 %s 没有 构造 方法，却收到了 %d 个参数"
                             % (cls.name, len(args)), line)
        return obj

    # ------------------------------------------------------------ 迭代
    def iter_items(self, it, line):
        if isinstance(it, list):
            return list(it)
        if isinstance(it, str):
            return list(it)
        if isinstance(it, dict):
            return list(it.keys())
        if isinstance(it, QlRange):
            return it.to_list()
        if isinstance(it, QlInstance):
            m = it.cls.find_method("__迭代__")
            if m:
                r = self.call_value(BoundMethod(it, m), [], {}, line, None)
                return self.iter_items(r, line)
        raise self.error("无法遍历 %s 类型的值" % ql_type(it), line,
                         hint="可遍历的类型：列表、字符串、字典（键）、区间")

    def _handle_catch(self, node, kind, val, env):
        """尝试把异常交给某个 捕获 分支，返回是否处理成功"""
        for tname, vname, blk in node.catches:
            if tname is None or tname == kind or tname in ("错误", "任意"):
                inner = Environment(env, "捕获")
                if vname:
                    inner.define(vname, val)
                self.visit(blk, inner)
                return True
        return False

    # ------------------------------------------------------------ 匹配
    def match_pattern(self, pat, subj, inner):
        if pat.kind == "wildcard":
            return True
        if pat.kind == "bind":
            inner.define(pat.name, subj)
            return True
        return self.deep_eq(pat.value, subj)

    # ------------------------------------------------------------ 模块
    def _lib_dirs(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return [self.base_dir, os.path.join(self.base_dir, "stdlib"),
                os.path.join(root, "stdlib")]

    def do_import(self, node, env):
        path = node.path.value if isinstance(node.path, A.Literal) else str(node.path)
        if node.is_file:
            mod = self.load_file_module(path, node.line)
        else:
            mod = B.get_builtin_module(path)
            if mod is None:
                # 退化为按文件名查找：当前目录、stdlib 子目录、项目 stdlib
                for d in self._lib_dirs():
                    cand = os.path.join(d, path + ".ql")
                    if os.path.exists(cand):
                        mod = self.load_file_module(cand, node.line)
                        break
            if mod is None:
                raise self.error("找不到模块 %r" % path, node.line,
                                 hint="内置模块：%s" % "、".join(
                                     [k for k in B.BUILTIN_MODULES.keys() if not k.isascii()]))
        if node.names:
            for n, alias in node.names:
                if n not in mod.exports:
                    raise self.error("模块 %s 没有导出 %r" % (mod.name, n), node.line)
                env.define(alias or n, mod.exports[n])
            return mod
        name = node.alias or os.path.splitext(os.path.basename(mod.name))[0]
        env.define(name, mod, True)
        return mod

    def load_file_module(self, path, line):
        p = path if os.path.isabs(path) else os.path.join(self.base_dir, path)
        p = os.path.abspath(p)
        if not p.endswith(".ql"):
            p += ".ql"
        if p in self.modules:
            return self.modules[p]
        if not os.path.exists(p):
            raise self.error("找不到模块文件：%s" % p, line)
        with open(p, "r", encoding="utf-8") as f:
            src = f.read()
        try:
            prog = parse(src, p)
        except QiuliError:
            raise
        menv = Environment(self.builtin_env, "模块:" + os.path.basename(p))
        old_fn, old_src, old_base = self.filename, self.source, self.base_dir
        self.filename, self.source, self.base_dir = p, src, os.path.dirname(p)
        try:
            self.visit(prog, menv)
        finally:
            self.filename, self.source, self.base_dir = old_fn, old_src, old_base
        exports = {}
        explicit = [s for s in prog.body if isinstance(s, A.ExportStmt)]
        if explicit:
            for st in explicit:
                for n in st.names:
                    v = menv.get(n)
                    if v is UNDEFINED:
                        raise self.error("模块 %s 导出了未定义的 %r" % (p, n), st.line)
                    exports[n] = v
        else:
            for s in prog.body:
                if isinstance(s, A.VarDecl):
                    exports[s.name] = menv.get(s.name)
                elif isinstance(s, A.FnDecl):
                    exports[s.name] = menv.get(s.name)
                elif isinstance(s, A.ClassDecl):
                    exports[s.name] = menv.get(s.name)
        for s in prog.body:
            if isinstance(s, (A.FnDecl, A.ClassDecl)) and getattr(s, "exported", False):
                exports[s.name] = menv.get(s.name)
        mod = QlModule(os.path.basename(p), exports, p)
        self.modules[p] = mod
        return mod

    # ------------------------------------------------------------ 字符串化
    def str_of(self, v):
        if isinstance(v, QlInstance):
            m = v.cls.find_method("__字符串__")
            if m:
                r = self.call_value(BoundMethod(v, m), [], {}, 0, None)
                return ql_str(r)
        return ql_str(v)
