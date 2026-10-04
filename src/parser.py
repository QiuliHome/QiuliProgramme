"""Qiuli 语法分析器：token 流 → AST（递归下降）。"""

from .errors import QiuliError
from .lexer import tokenize, RESERVED
from . import ast_nodes as A

# ------------------------------------------------------------ 优先级表
ASSIGN_OPS = ("=", "+=", "-=", "*=", "/=", "%=", "**=", "//=")


class Parser:
    def __init__(self, tokens, filename="<input>", source=""):
        self.toks = tokens
        self.pos = 0
        self.filename = filename
        self.source = source

    # -------------------------------------------------- 工具
    def peek(self, k=0):
        j = self.pos + k
        return self.toks[j] if j < len(self.toks) else self.toks[-1]

    def prev(self):
        return self.toks[max(self.pos - 1, 0)]

    def next(self):
        t = self.peek()
        if t.type != "EOF":
            self.pos += 1
        return t

    def at(self, type_, *values):
        t = self.peek()
        if t.type != type_:
            return False
        return (not values) or (t.value in values)

    def at_op(self, *v):
        return self.at("OP", *v)

    def at_kw(self, *v):
        return self.at("KEYWORD", *v)

    def accept(self, type_, *values):
        if self.at(type_, *values):
            return self.next()
        return None

    def accept_op(self, *v):
        return self.accept("OP", *v)

    def accept_kw(self, *v):
        return self.accept("KEYWORD", *v)

    def expect_op(self, v, msg=None):
        if not self.at_op(v):
            t = self.peek()
            raise self.err(msg or "期望 %r，实际得到 %r" % (v, self._desc(t)), t)
        return self.next()

    def expect_kw(self, v, msg=None):
        if not self.at_kw(v):
            t = self.peek()
            raise self.err(msg or "期望关键字 %r，实际得到 %r" % (v, self._desc(t)), t)
        return self.next()

    def expect_ident(self, msg="期望一个名字"):
        t = self.peek()
        if t.type == "IDENT":
            return self.next().value
        if t.type == "KEYWORD":
            return self.next().value      # 允许关键字当名字（如 obj.fn）
        raise self.err("%s，实际得到 %r" % (msg, self._desc(t)), t)

    def _desc(self, t):
        if t.type == "EOF":
            return "文件结尾"
        if t.type == "NEWLINE":
            return "换行"
        return t.value

    def err(self, msg, tok=None, hint=None):
        tok = tok or self.peek()
        return QiuliError("语法错误", msg, self.filename, tok.line, tok.col,
                          self.source, hint)

    def skip_newlines(self):
        while self.at("NEWLINE"):
            self.next()

    def eat_terminator(self):
        """语句结束：换行 / 分号 / } / EOF，或与下一条语句同行（隐式分号）"""
        if self.at("NEWLINE"):
            self.next()
            return
        if self.at_op("}") or self.at("EOF"):
            return
        # 同一行里紧接着写第二条语句时自动补分号：{ 输出(1) 输出(2) }
        prev = self.prev()
        cur = self.peek()
        if prev is not cur and getattr(prev, "line", 0) == getattr(cur, "line", -1):
            return
        t = self.peek()
        raise self.err("语句未结束，期望换行或分号，实际得到 %r" % self._desc(t), t)

    # -------------------------------------------------- 顶层
    def parse_program(self):
        body = []
        self.skip_newlines()
        while not self.at("EOF"):
            s = self.parse_statement()
            if s is not None:
                body.append(s)
            self.skip_newlines()
        return A.Program(body=body)

    def parse_block(self):
        self.expect_op("{", "期望 { 开始一个代码块")
        self.skip_newlines()
        body = []
        while not self.at_op("}") and not self.at("EOF"):
            s = self.parse_statement()
            if s is not None:
                body.append(s)
            self.skip_newlines()
        self.expect_op("}", "代码块缺少结尾的 }")
        return A.Block(body=body)

    # -------------------------------------------------- 语句
    def parse_statement(self):
        t = self.peek()

        # 块级语句
        if t.type == "KEYWORD":
            v = t.value
            if v == "if":
                return self.parse_if()
            if v == "while":
                return self.parse_while()
            if v == "for":
                return self.parse_for()
            if v == "try":
                return self.parse_try()
            if v == "match":
                return self.parse_match()
            if v == "fn":
                return self.parse_fn()
            if v == "class":
                return self.parse_class()
            if v == "let":
                return self.parse_var(False)
            if v == "const":
                return self.parse_var(True)
            if v == "return":
                return self.parse_return()
            if v == "break":
                self.next()
                self.eat_terminator()
                return A.BreakStmt(line=t.line)
            if v == "continue":
                self.next()
                self.eat_terminator()
                return A.ContinueStmt(line=t.line)
            if v == "throw":
                self.next()
                val = self.parse_expression()
                self.eat_terminator()
                return A.ThrowStmt(value=val, line=t.line)
            if v == "import":
                return self.parse_import()
            if v == "from":
                return self.parse_from_import()
            if v == "export":
                return self.parse_export()

        # 类 / 函数 / 变量声明前的 导出 修饰已在上面处理
        if t.type == "OP" and t.value == "{":
            return self.parse_block()

        # 表达式语句 / 赋值
        e = self.parse_expression()
        self.eat_terminator()
        return A.ExprStmt(expr=e, line=e.line if hasattr(e, "line") else t.line)

    # -------------------------------------------------- 各类语句
    def parse_var(self, const):
        kw = self.next()
        decls = []
        while True:
            name_tok = self.peek()
            name = self.expect_ident("变量需要一个名字")
            init = None
            if self.accept_op("="):
                init = self.parse_expression()
            decls.append(A.VarDecl(name=name, init=init, const=const,
                                   line=name_tok.line))
            if not self.accept_op(","):
                break
        self.eat_terminator()
        if len(decls) == 1:
            return decls[0]
        return A.Block(body=decls, line=kw.line)

    def parse_return(self):
        t = self.next()
        if self.at("NEWLINE") or self.at_op("}") or self.at("EOF"):
            self.eat_terminator()
            return A.ReturnStmt(value=None, line=t.line)
        v = self.parse_expression()
        self.eat_terminator()
        return A.ReturnStmt(value=v, line=t.line)

    # ---- 函数
    def parse_fn(self, is_method=False, name_override=None):
        static = False
        if name_override is None:
            kw = self.next()                      # 消耗 fn / method
            if self.at_kw("static"):
                self.next()
                static = True
            name = self.expect_ident("函数需要一个名字")
        else:
            kw = self.peek()                      # 名字已由类体解析，当前是 (
            name = name_override
        params = self.parse_params()
        # 单表达式函数：fn f(x) => expr
        if self.accept_op("=>"):
            body = self.parse_expression()
            self.eat_terminator()
            return A.FnDecl(name=name, params=params, body=body,
                            expr_body=True, is_method=is_method,
                            is_static=static, line=kw.line)
        block = self.parse_block()
        return A.FnDecl(name=name, params=params, body=block,
                        expr_body=False, is_method=is_method,
                        is_static=static, line=kw.line)

    def parse_params(self):
        self.expect_op("(", "函数参数列表应以 ( 开始")
        params = []
        while not self.at_op(")"):
            if self.accept_op("*"):
                n = self.expect_ident("可变参数需要一个名字")
                params.append(A.Param(name=n, vararg=True))
                self.accept_op(",")
                break
            n = self.expect_ident("参数需要一个名字")
            default = None
            if self.accept_op("="):
                default = self.parse_expression()
            params.append(A.Param(name=n, default=default))
            if not self.accept_op(","):
                break
        self.expect_op(")", "函数参数列表缺少结尾的 )")
        return params

    # ---- 类
    def parse_class(self):
        kw = self.next()
        name = self.expect_ident("类需要一个名字")
        sup = None
        if self.accept_kw("extends"):
            sup = A.Ident(name=self.expect_ident("父类需要一个名字"), line=kw.line)
        self.expect_op("{", "类体应以 { 开始")
        self.skip_newlines()
        methods = []
        fields = []
        while not self.at_op("}") and not self.at("EOF"):
            # 静态成员
            static = False
            if self.at_kw("static"):
                self.next()
                static = True
            if self.at_kw("init"):
                self.next()
                params = self.parse_params()
                body = self.parse_block()
                m = A.FnDecl(name="init", params=params, body=body,
                             is_method=True, line=kw.line)
                methods.append(m)
            elif self.at_kw("fn") or self.at_kw("method"):
                m = self.parse_fn(is_method=True)
                m.is_static = static
                methods.append(m)
            elif self.peek().type in ("IDENT", "KEYWORD") and self.peek(1).type == "OP" \
                    and self.peek(1).value == "(":
                nm = self.expect_ident()
                m = self.parse_fn(is_method=True, name_override=nm)
                m.is_static = static or (nm == "init")
                methods.append(m)
            elif self.at_kw("let") or self.at_kw("const"):
                d = self.parse_var(self.at_kw("const"))
                fields.append(d)
            else:
                t = self.peek()
                raise self.err("类体中只支持方法、构造或字段声明，实际得到 %r" % self._desc(t), t)
            self.skip_newlines()
        self.expect_op("}", "类体缺少结尾的 }")
        return A.ClassDecl(name=name, superclass=sup, methods=methods,
                           fields=fields, line=kw.line)

    # ---- if
    def parse_if(self):
        kw = self.next()
        cond = self.parse_expression()
        then_block = self.parse_block()
        elifs = []
        else_block = None
        self.skip_newlines()
        while self.at_kw("elif"):
            self.next()
            c = self.parse_expression()
            b = self.parse_block()
            elifs.append((c, b))
            self.skip_newlines()
        if self.accept_kw("else"):
            if self.at_kw("if"):
                self.next()
                c = self.parse_expression()
                else_block = A.Block(body=[A.IfStmt(cond=c, then_block=self.parse_block(),
                                                    line=c.line)], line=c.line)
            else:
                else_block = self.parse_block()
        return A.IfStmt(cond=cond, then_block=then_block, elifs=elifs,
                        else_block=else_block, line=kw.line)

    # ---- while
    def parse_while(self):
        kw = self.next()
        cond = self.parse_expression()
        body = self.parse_block()
        return A.WhileStmt(cond=cond, body=body, line=kw.line)

    # ---- for
    def parse_for(self):
        kw = self.next()
        v1 = self.expect_ident("遍历需要一个循环变量名")
        index_var = None
        if self.accept_op(","):
            index_var = v1
            v1 = self.expect_ident("遍历需要第二个变量名")
        if not (self.at_kw("in") or self.at_op("in")):
            t = self.peek()
            raise self.err("遍历语句缺少 于/in，实际得到 %r" % self._desc(t), t)
        self.next()
        it = self.parse_expression()
        body = self.parse_block()
        return A.ForStmt(var=v1, iterable=it, body=body,
                         index_var=index_var, line=kw.line)

    # ---- try
    def parse_try(self):
        kw = self.next()
        body = self.parse_block()
        catches = []
        self.skip_newlines()
        while self.at_kw("catch"):
            self.next()
            type_name = None
            var_name = None
            if self.peek().type in ("IDENT", "KEYWORD"):
                first = self.next().value
                if self.accept_kw("as"):
                    type_name = first
                    var_name = self.expect_ident("捕获变量需要一个名字")
                else:
                    var_name = first
            blk = self.parse_block()
            catches.append((type_name, var_name, blk))
            self.skip_newlines()
        fin = None
        if self.accept_kw("finally"):
            fin = self.parse_block()
        if not catches and fin is None:
            raise self.err("尝试语句至少需要 捕获 或 最终 之一", kw)
        return A.TryStmt(body=body, catches=catches, finally_block=fin, line=kw.line)

    # ---- match
    def parse_match(self):
        kw = self.next()
        subject = self.parse_expression()
        self.expect_op("{", "匹配体应以 { 开始")
        self.skip_newlines()
        cases = []
        default = None
        while not self.at_op("}") and not self.at("EOF"):
            if self.accept_kw("case"):
                pat = self.parse_pattern()
                blk = self.parse_block()
                cases.append((pat, blk))
            elif self.accept_kw("default"):
                default = self.parse_block()
            else:
                t = self.peek()
                raise self.err("匹配体内只支持 情形 或 默认，实际得到 %r" % self._desc(t), t)
            self.skip_newlines()
        self.expect_op("}", "匹配体缺少结尾的 }")
        return A.MatchStmt(subject=subject, cases=cases, default=default, line=kw.line)

    def parse_pattern(self):
        t = self.peek()
        if t.type == "IDENT" and t.value == "_":
            self.next()
            return A.Pattern(kind="wildcard", line=t.line)
        if t.type == "IDENT":
            self.next()
            return A.Pattern(kind="bind", name=t.value, line=t.line)
        v = self.parse_primary()
        if isinstance(v, A.Literal):
            return A.Pattern(kind="literal", value=v.value, line=t.line)
        return A.Pattern(kind="literal", value=v, line=t.line)

    # ---- import / export
    def parse_import(self):
        kw = self.next()
        if self.peek().type == "STRING":
            path = self.next().value
        else:
            path = self.expect_ident("导入需要一个模块名或路径字符串")
        alias = None
        if self.accept_kw("as"):
            alias = self.expect_ident("别名需要一个名字")
        self.eat_terminator()
        is_file = isinstance(path, str) and (
            path.startswith("./") or path.startswith("../") or
            path.startswith("/") or path.endswith(".ql") or "\\" in path)
        return A.ImportStmt(path=A.Literal(value=path, line=kw.line),
                            alias=alias, is_file=is_file, line=kw.line)

    def parse_from_import(self):
        kw = self.next()   # from
        if self.peek().type == "STRING":
            path = self.next().value
        else:
            path = self.expect_ident()
        self.expect_kw("import", "从…导入 语句缺少 导入/import")
        names = []
        while True:
            n = self.expect_ident()
            alias = None
            if self.accept_kw("as"):
                alias = self.expect_ident()
            names.append((n, alias))
            if not self.accept_op(","):
                break
        self.eat_terminator()
        is_file = isinstance(path, str) and (
            path.startswith("./") or path.startswith("../") or
            path.startswith("/") or path.endswith(".ql"))
        return A.ImportStmt(path=A.Literal(value=path, line=kw.line),
                            names=names, is_file=is_file, line=kw.line)

    def parse_export(self):
        kw = self.next()
        # 导出 函数 f() ...
        if self.at_kw("fn"):
            f = self.parse_fn()
            f.exported = True
            f.line = kw.line
            return f
        if self.at_kw("class"):
            c = self.parse_class()
            c.exported = True
            return c
        names = []
        while True:
            names.append(self.expect_ident("导出需要一个名字"))
            if not self.accept_op(","):
                break
        self.eat_terminator()
        return A.ExportStmt(names=names, line=kw.line)

    # ================================================== 表达式
    def parse_expression(self):
        return self.parse_assignment()

    def parse_assignment(self):
        start = self.pos
        left = self.parse_ternary()
        t = self.peek()
        if t.type == "OP" and t.value in ASSIGN_OPS:
            self.next()
            if not isinstance(left, (A.Ident, A.Index, A.Member)):
                self.pos = start
                raise self.err("赋值号左边必须是变量、下标或成员", t)
            rhs = self.parse_assignment()
            return A.Assign(target=left, value=rhs, op=t.value, line=t.line)
        return left

    def parse_ternary(self):
        cond = self.parse_or()
        if self.accept_op("?"):
            a = self.parse_ternary()
            self.expect_op(":", "三元表达式缺少 :")
            b = self.parse_ternary()
            return A.Ternary(cond=cond, a=a, b=b, line=cond.line)
        return cond

    def parse_or(self):
        left = self.parse_and()
        while self.at_kw("or") or self.at_op("||"):
            self.next()
            right = self.parse_and()
            left = A.Logical(op="or", left=left, right=right, line=left.line)
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.at_kw("and") or self.at_op("&&"):
            self.next()
            right = self.parse_not()
            left = A.Logical(op="and", left=left, right=right, line=left.line)
        return left

    def parse_not(self):
        if self.at_kw("not") or self.at_op("!"):
            t = self.next()
            r = self.parse_not()
            return A.Unary(op="not", right=r, line=t.line)
        return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_range()
        while self.at_op("==", "!=", "<", "<=", ">", ">="):
            op = self.next().value
            right = self.parse_range()
            left = A.Binary(op=op, left=left, right=right, line=left.line)
        return left

    def parse_range(self):
        left = self.parse_pipe()
        if self.at_op("..", "..<"):
            op = self.next().value
            right = self.parse_pipe()
            return A.Range(start=left, end=right, inclusive=(op == ".."),
                           line=left.line)
        return left

    def parse_pipe(self):
        left = self.parse_additive()
        while self.at_op("|>"):
            self.next()
            right = self.parse_additive()
            if isinstance(right, A.Call):
                # 管道把左侧的值作为「最后一个」实参传入，
                # 以配合 映射(函数, 数据) 这类中文语序的内置函数
                right.args.append(left)
                left = right
            else:
                left = A.Call(callee=right, args=[left], line=left.line)
        return left

    def parse_additive(self):
        left = self.parse_multiplicative()
        while self.at_op("+", "-"):
            op = self.next().value
            right = self.parse_multiplicative()
            left = A.Binary(op=op, left=left, right=right, line=left.line)
        return left

    def parse_multiplicative(self):
        left = self.parse_unary()
        while self.at_op("*", "/", "%", "//"):
            op = self.next().value
            right = self.parse_unary()
            left = A.Binary(op=op, left=left, right=right, line=left.line)
        return left

    def parse_unary(self):
        if self.at_op("-", "+", "~"):
            t = self.next()
            r = self.parse_unary()
            return A.Unary(op="-" if t.value == "-" else t.value, right=r, line=t.line)
        return self.parse_power()

    def parse_power(self):
        base = self.parse_postfix()
        if self.at_op("**"):
            t = self.next()
            exp = self.parse_unary()
            return A.Binary(op="**", left=base, right=exp, line=t.line)
        return base

    def parse_postfix(self):
        e = self.parse_primary()
        while True:
            if self.at_op("("):
                args, named = self.parse_args()
                e = A.Call(callee=e, args=args, named=named, line=e.line)
            elif self.at_op("."):
                dot = self.next()
                nm = self.expect_ident("成员名")
                e = A.Member(obj=e, name=nm, line=dot.line)
            elif self.at_op("?."):
                dot = self.next()
                nm = self.expect_ident("成员名")
                e = A.Member(obj=e, name=nm, safe=True, line=dot.line)
            elif self.at_op("["):
                self.next()
                # 切片?
                if self.at_op(":"):
                    self.next()
                    end = None if self.at_op("]") else self.parse_expression()
                    self.expect_op("]")
                    e = A.Slice(obj=e, start=None, end=end, line=e.line)
                else:
                    first = self.parse_expression()
                    if self.at_op(":"):
                        self.next()
                        end = None if self.at_op("]") else self.parse_expression()
                        self.expect_op("]")
                        e = A.Slice(obj=e, start=first, end=end, line=e.line)
                    else:
                        self.expect_op("]", "下标缺少结尾的 ]")
                        e = A.Index(obj=e, key=first, line=e.line)
            else:
                break
        return e

    def parse_args(self):
        self.expect_op("(")
        args = []
        named = {}
        while not self.at_op(")"):
            # 命名参数： IDENT '=' expr （排除 == ）
            if self.peek().type == "IDENT" and self.peek(1).type == "OP" \
                    and self.peek(1).value == "=":
                nm = self.next().value
                self.next()
                named[nm] = self.parse_expression()
            else:
                args.append(self.parse_expression())
            if not self.accept_op(","):
                break
        self.expect_op(")", "参数列表缺少结尾的 )")
        return args, named

    # ---- 原子
    def parse_primary(self):
        t = self.peek()

        if t.type == "NUMBER":
            self.next()
            return A.Literal(value=t.value, line=t.line)

        if t.type == "STRING":
            self.next()
            return self.build_string(t)

        if t.type == "OP" and t.value == "(":
            # 可能是 lambda：(a, b) => ...
            if self.lambda_ahead():
                return self.parse_lambda()
            self.next()
            e = self.parse_expression()
            if self.at_op(","):     # 元组（用列表表示）
                items = [e]
                while self.accept_op(","):
                    items.append(self.parse_expression())
                self.expect_op(")")
                return A.ListExpr(items=items, line=t.line)
            self.expect_op(")", "括号缺少结尾的 )")
            return e

        if t.type == "OP" and t.value == "[":
            self.next()
            items = []
            while not self.at_op("]"):
                items.append(self.parse_expression())
                if not self.accept_op(","):
                    break
            self.expect_op("]", "列表缺少结尾的 ]")
            return A.ListExpr(items=items, line=t.line)

        if t.type == "OP" and t.value == "{":
            return self.parse_dict()

        if t.type == "KEYWORD":
            v = t.value
            if v == "true":
                self.next()
                return A.Literal(value=True, line=t.line)
            if v == "false":
                self.next()
                return A.Literal(value=False, line=t.line)
            if v == "nil":
                self.next()
                return A.Literal(value=None, line=t.line)
            if v == "fn":
                # 匿名函数：fn(x) { ... } / fn(x) => expr
                kw = self.next()
                params = self.parse_params()
                if self.accept_op("=>"):
                    body = self.parse_expression()
                    return A.Lambda(params=params, body=body, expr_body=True, line=kw.line)
                body = self.parse_block()
                return A.Lambda(params=params, body=body, expr_body=False, line=kw.line)
            if v == "self":
                self.next()
                return A.SelfExpr(line=t.line)
            if v == "super":
                self.next()
                m = None
                if self.at_op("."):
                    self.next()
                    m = self.expect_ident()
                return A.SuperExpr(method=m, line=t.line)
            if v == "init":
                self.next()
                return A.Ident(name="init", line=t.line)

        if t.type == "IDENT":
            # lambda：x => expr
            if self.peek(1).type == "OP" and self.peek(1).value == "=>":
                return self.parse_lambda()
            self.next()
            return A.Ident(name=t.value, line=t.line)

        raise self.err("意外的符号 %r" % self._desc(t), t)

    def lambda_ahead(self):
        """判断 '(' 开头是否为 lambda：扫描到匹配 ')' 后跟 '=>'"""
        depth = 0
        i = self.pos
        while i < len(self.toks):
            tk = self.toks[i]
            if tk.type == "EOF":
                return False
            if tk.type == "OP":
                if tk.value == "(":
                    depth += 1
                elif tk.value == ")":
                    depth -= 1
                    if depth == 0:
                        nxt = self.toks[i + 1] if i + 1 < len(self.toks) else None
                        return bool(nxt and nxt.type == "OP" and nxt.value == "=>")
                elif tk.value == "{" or tk.value == ";" or tk.value == "\n":
                    return False
            i += 1
        return False

    def parse_lambda(self):
        t = self.peek()
        if self.at_op("("):
            self.next()
            params = []
            while not self.at_op(")"):
                if self.accept_op("*"):
                    params.append(A.Param(name=self.expect_ident(), vararg=True))
                    break
                n = self.expect_ident()
                d = None
                if self.accept_op("="):
                    d = self.parse_expression()
                params.append(A.Param(name=n, default=d))
                if not self.accept_op(","):
                    break
            self.expect_op(")")
        else:
            params = [A.Param(name=self.expect_ident())]
        self.expect_op("=>", "箭头函数缺少 =>")
        if self.at_op("{"):
            body = self.parse_block()
            return A.Lambda(params=params, body=body, expr_body=False, line=t.line)
        body = self.parse_expression()
        return A.Lambda(params=params, body=body, expr_body=True, line=t.line)

    def parse_dict(self):
        t = self.next()   # {
        keys, values = [], []
        while not self.at_op("}"):
            k = self.parse_expression()
            if not (self.accept_op(":") or self.accept_op("=>")):
                tk = self.peek()
                raise self.err("字典键值之间需要 : ，实际得到 %r" % self._desc(tk), tk)
            v = self.parse_expression()
            keys.append(k)
            values.append(v)
            if not self.accept_op(","):
                break
        self.expect_op("}", "字典缺少结尾的 }")
        return A.DictExpr(keys=keys, values=values, line=t.line)

    # ---- 字符串插值
    def build_string(self, tok):
        s = tok.value
        if "${" not in s:
            return A.Literal(value=s, line=tok.line)
        parts = []
        buf = []
        i = 0
        while i < len(s):
            if s.startswith("${", i):
                # 找到与 ${ 匹配的 }（跳过插值内的字符串与嵌套花括号）
                j = i + 2
                depth = 1
                while j < len(s) and depth > 0:
                    ch = s[j]
                    if ch in "\"'":
                        q = ch
                        j += 1
                        while j < len(s) and s[j] != q:
                            if s[j] == "\\":
                                j += 1
                            j += 1
                        j += 1
                        continue
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                if depth > 0:
                    raise self.err("字符串插值 ${...} 缺少结尾的 }", tok)
                if buf:
                    parts.append(A.Literal(value="".join(buf), line=tok.line))
                    buf = []
                code = s[i + 2:j]
                sub = Parser(tokenize(code, self.filename),
                             self.filename, self.source)
                parts.append(sub.parse_expression())
                i = j + 1
            else:
                buf.append(s[i])
                i += 1
        if buf:
            parts.append(A.Literal(value="".join(buf), line=tok.line))
        return A.InterpString(parts=parts, line=tok.line)


def parse(source, filename="<input>"):
    toks = tokenize(source, filename)
    p = Parser(toks, filename, source)
    return p.parse_program()
