"""Qiuli 抽象语法树（AST）节点定义。"""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class Node:
    line: int = 0

    def children(self):
        for k, v in self.__dict__.items():
            if k == "line":
                continue
            if isinstance(v, Node):
                yield (k, v)
            elif isinstance(v, (list, tuple)):
                for item in v:
                    if isinstance(item, Node):
                        yield (k, item)

    def dump(self, indent=0):
        pad = "  " * indent
        name = type(self).__name__
        extra = []
        for k, v in self.__dict__.items():
            if k in ("line",):
                continue
            if isinstance(v, Node) or (isinstance(v, (list, tuple)) and any(isinstance(i, Node) for i in v)):
                continue
            if isinstance(v, str):
                extra.append("%s=%r" % (k, v))
            else:
                extra.append("%s=%s" % (k, v))
        head = "%s%s%s" % (pad, name, ("  " + " ".join(extra)) if extra else "")
        out = [head]
        for _, ch in self.children():
            out.append(ch.dump(indent + 1))
        return "\n".join(out)


# ------------------------------------------------------------------ 语句
@dataclass
class Program(Node):
    body: List[Node] = field(default_factory=list)


@dataclass
class Block(Node):
    body: List[Node] = field(default_factory=list)


@dataclass
class VarDecl(Node):
    name: str = ""
    init: Optional[Node] = None
    const: bool = False


@dataclass
class Assign(Node):
    target: Optional[Node] = None
    value: Optional[Node] = None
    op: str = "="


@dataclass
class Param:
    name: str
    default: Optional[Node] = None
    vararg: bool = False


@dataclass
class FnDecl(Node):
    name: str = ""
    params: List[Param] = field(default_factory=list)
    body: Optional[Node] = None      # Block 或 单表达式
    expr_body: bool = False
    is_method: bool = False
    is_static: bool = False
    exported: bool = False


@dataclass
class Lambda(Node):
    params: List[Param] = field(default_factory=list)
    body: Optional[Node] = None
    expr_body: bool = True


@dataclass
class ClassDecl(Node):
    name: str = ""
    superclass: Optional[Node] = None
    methods: List[FnDecl] = field(default_factory=list)
    fields: List[Node] = field(default_factory=list)
    exported: bool = False


@dataclass
class IfStmt(Node):
    cond: Optional[Node] = None
    then_block: Optional[Node] = None
    elifs: list = field(default_factory=list)     # [(cond, block)]
    else_block: Optional[Node] = None


@dataclass
class WhileStmt(Node):
    cond: Optional[Node] = None
    body: Optional[Node] = None


@dataclass
class ForStmt(Node):
    var: str = ""
    iterable: Optional[Node] = None
    body: Optional[Node] = None
    index_var: Optional[str] = None


@dataclass
class BreakStmt(Node):
    pass


@dataclass
class ContinueStmt(Node):
    pass


@dataclass
class ReturnStmt(Node):
    value: Optional[Node] = None


@dataclass
class TryStmt(Node):
    body: Optional[Node] = None
    catches: list = field(default_factory=list)   # [(name|None, varname, block)]
    finally_block: Optional[Node] = None


@dataclass
class ThrowStmt(Node):
    value: Optional[Node] = None


@dataclass
class ImportStmt(Node):
    path: Optional[Node] = None      # String 或 标识符
    alias: Optional[str] = None
    names: list = field(default_factory=list)     # 从模块导入的具体名字
    is_file: bool = False


@dataclass
class ExportStmt(Node):
    names: list = field(default_factory=list)


@dataclass
class ExprStmt(Node):
    expr: Optional[Node] = None


# ------------------------------------------------------------------ 表达式
@dataclass
class Literal(Node):
    value: Any = None


@dataclass
class Ident(Node):
    name: str = ""


@dataclass
class SelfExpr(Node):
    pass


@dataclass
class SuperExpr(Node):
    method: Optional[str] = None


@dataclass
class ListExpr(Node):
    items: List[Node] = field(default_factory=list)


@dataclass
class DictExpr(Node):
    keys: List[Node] = field(default_factory=list)
    values: List[Node] = field(default_factory=list)


@dataclass
class Index(Node):
    obj: Optional[Node] = None
    key: Optional[Node] = None


@dataclass
class Slice(Node):
    obj: Optional[Node] = None
    start: Optional[Node] = None
    end: Optional[Node] = None


@dataclass
class Call(Node):
    callee: Optional[Node] = None
    args: List[Node] = field(default_factory=list)
    named: dict = field(default_factory=dict)     # name -> expr


@dataclass
class Member(Node):
    obj: Optional[Node] = None
    name: str = ""
    safe: bool = False


@dataclass
class Binary(Node):
    op: str = ""
    left: Optional[Node] = None
    right: Optional[Node] = None


@dataclass
class Unary(Node):
    op: str = ""
    right: Optional[Node] = None


@dataclass
class Logical(Node):
    op: str = ""
    left: Optional[Node] = None
    right: Optional[Node] = None


@dataclass
class Ternary(Node):
    cond: Optional[Node] = None
    a: Optional[Node] = None
    b: Optional[Node] = None


@dataclass
class Range(Node):
    start: Optional[Node] = None
    end: Optional[Node] = None
    inclusive: bool = True


@dataclass
class InterpString(Node):
    parts: List[Node] = field(default_factory=list)   # Literal(str) 或 表达式


@dataclass
class MatchStmt(Node):
    subject: Optional[Node] = None
    cases: list = field(default_factory=list)         # [(pattern_node, block)]
    default: Optional[Node] = None


@dataclass
class Pattern(Node):
    """匹配模式：字面量 / 通配符 _ / 绑定变量 / 类型"""
    kind: str = "literal"     # literal | wildcard | bind | type
    value: Any = None
    name: str = ""
