"""Qiuli 交互式环境（REPL）。"""

import os
import sys

from . import ast_nodes as A
from .environment import Environment
from .errors import QiuliError, QiuliRuntimeError, QiuliThrow
from .lexer import tokenize
from .objects import ql_repr
from .parser import parse

PROMPT = "ql> "
CONT = "... "


def is_complete(src):
    """判断一段代码是否已经写完整（用于 REPL 多行输入）"""
    try:
        toks = tokenize(src)
    except Exception:
        return False
    depth = 0
    for t in toks:
        if t.type == "OP" and t.value in ("(", "[", "{"):
            depth += 1
        elif t.type == "OP" and t.value in (")", "]", "}"):
            depth -= 1
        elif t.type == "KEYWORD" and t.value in ("if", "while", "for", "fn",
                                                 "class", "try", "match"):
            # 关键字后若没有 { 也认为需要继续（同一行写满的情况由 depth 判断）
            pass
    return depth <= 0


class REPL:
    def __init__(self, interp, use_color=True):
        self.interp = interp
        self.env = interp.global_env
        self.use_color = use_color
        self.history = []

    # ---------------------------------------------------------- 颜色
    def c(self, text, code):
        if not self.use_color:
            return text
        return "\033[%sm%s\033[0m" % (code, text)

    # ---------------------------------------------------------- 主循环
    def loop(self):
        self.banner()
        buf = []
        while True:
            try:
                prompt = CONT if buf else PROMPT
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                print()
                print(self.c("再见！", "90"))
                break
            if line.strip() == "":
                if buf:
                    buf.append(line)
                continue
            stripped = line.strip()
            if not buf and stripped.startswith(":"):
                if self.command(stripped):
                    continue
                break
            buf.append(line)
            src = "\n".join(buf)
            if not is_complete(src):
                continue
            buf = []
            self.run_once(src)

    def banner(self):
        from . import __version__
        print(self.c("  ┌─────────────────────────────┐", "93"))
        print(self.c("  │   Qiuli %s  ·  .ql          │" % __version__, "93"))
        print(self.c("  └─────────────────────────────┘", "93"))
        print(self.c("  输入 :帮助 查看命令，:退出 或 Ctrl+D 离开\n", "90"))

    def command(self, cmd):
        c = cmd[1:].strip()
        if c in ("退出", "exit", "quit", "q"):
            return False
        if c in ("帮助", "help", "?"):
            print(self.c("""
  REPL 命令
    :帮助              显示本帮助
    :退出              离开 REPL（Ctrl+D 亦可）
    :变量              列出当前已定义的变量
    :清屏              清屏
    :示例              显示一段示例代码
    :历史              显示本次输入过的代码

  语言速记
    让 x = 1            常量 y = 2
    函数 加(a, b) { 返回 a + b }
    类 人 { 构造(名) { 自身.名 = 名 } }
    如果 x > 0 { 输出("正数") } 否则 { 输出("非正") }
    遍历 i 于 范围(3) { 输出(i) }
    遍历 k, v 于 {"a": 1} { 输出(k, v) }
    [1,2,3] |> 映射(x => x*2) |> 输出
""", "36"))
            return True
        if c in ("变量", "vars"):
            names = sorted(self.env.vars.keys())
            if not names:
                print(self.c("（当前作用域没有变量）", "90"))
            for n in names:
                print("  %-20s = %s" % (n, ql_repr(self.env.vars[n])))
            return True
        if c in ("清屏", "clear", "cls"):
            os.system("cls" if os.name == "nt" else "clear")
            return True
        if c in ("历史", "history"):
            for i, h in enumerate(self.history[-20:], 1):
                print("  %2d  %s" % (i, h.replace("\n", " ⏎ ")))
            return True
        if c in ("示例", "demo"):
            print(self.c("""
  让 名单 = ["小明", "小红", "小刚"]
  遍历 i, 人 于 名单 {
      输出("第 ${i+1} 位：${人}")
  }
  让 平方 = x => x ** 2
  输出(映射(平方, 范围(1, 6)))
""", "36"))
            return True
        print(self.c("未知命令：%s（试试 :帮助）" % cmd, "31"))
        return True

    # ---------------------------------------------------------- 执行
    def run_once(self, src):
        self.history.append(src)
        self.interp.filename = "<交互>"
        self.interp.source = src
        try:
            prog = parse(src, "<交互>")
        except QiuliError as e:
            print(e.render(self.use_color))
            return
        try:
            last = prog.body[-1] if prog.body else None
            value = None
            show = isinstance(last, A.ExprStmt) and \
                not (hasattr(last.expr, "callee") and getattr(last.expr.callee, "name", "") == "输出")
            for i, stmt in enumerate(prog.body):
                if i == len(prog.body) - 1 and show:
                    value = self.interp.visit(last.expr, self.env)
                else:
                    self.interp.visit(stmt, self.env)
            if show and value is not None:
                print(self.c("→ " + ql_repr(value), "92"))
        except QiuliThrow as e:
            from .objects import ql_str
            print(self.c("未捕获的抛出：" + (e.value.message if hasattr(e.value, "message") else ql_str(e.value)), "31"))
        except QiuliRuntimeError as e:
            print(e.render(self.use_color))
        except KeyboardInterrupt:
            print(self.c("（已中断）", "31"))
        except RecursionError:
            print(self.c("递归过深", "31"))
        finally:
            self.interp.call_stack.clear()
