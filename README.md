# Qiuli（.ql）

> 一门为中文设计的脚本语言。关键字有中文和英文两套，读起来像句子。
> 零依赖、纯 Python 实现、可离线运行。

```ql
# 你好，世界
让 名字 = "世界"
输出("你好，${名字}！")

# 函数、列表、管道
函数 平方(x) => x * x
让 结果 = 范围(1, 11) |> 过滤(x => x % 2 == 0) |> 映射(平方) |> 求和()
输出("1~10 偶数的平方和 =", 结果)     # 220

# 类与继承
类 猫 继承 动物 {
    构造(名字) { 父.init(名字) }
    发声() => "喵喵"
}
```

---

## 快速开始

需要 **Python 3.8+**（无需安装任何第三方库）。

```bash
# 1. 运行一个脚本
python qiuli.py examples/01_你好世界.ql

# 2. 进入交互式环境（REPL）
python qiuli.py

# 3. 只做语法检查（不执行）
python qiuli.py check 我的脚本.ql

# 4. 跑测试看看一切是否正常
python qiuli.py test
```

### 已经配好了：直接用 `qiuli` 命令

本机已把项目目录加入用户 PATH，**新开一个终端**后可以在任意目录直接用：

```bash
qiuli                    # 进入 REPL
qiuli 01_你好世界         # 跑示例（不用写路径，也不用写 .ql）
qiuli 示例               # 看看有哪些示例可以跑
qiuli 我的脚本.ql        # 跑自己的脚本
```

> 如果提示 `qiuli : 无法将"qiuli"项识别为...`，说明终端还是旧的环境变量 ——
> 关掉重开一个终端即可。也可以自己在其他机器上跑
> `powershell -ExecutionPolicy Bypass -File install.ps1` 完成同样的配置。

Windows 用户也可以直接双击 **`qiuli.bat`** 进入 REPL，
或把 `.ql` 脚本拖到 `qiuli.bat` 上运行。

---

## 语言特性一览

| 方面 | 支持情况 |
| --- | --- |
| 变量 | `让`（可改）、`常量`（不可改），块级作用域 |
| 类型 | 数字、字符串、布尔、空、列表、字典、函数、类、对象、模块、区间 |
| 运算 | `+ - * / // % **`、比较、逻辑（`且 或 非`）、区间 `..`、`??`、`?:` |
| 函数 | 默认参数、命名参数、可变参数 `*args`、lambda `x => ...`、闭包、递归 |
| 面向对象 | 类、继承、`自身`/self、`父`/super、运算符重载、`__字符串__` |
| 控制流 | `如果/又如果/否则`、`当`、`遍历`、`中断/继续`、`匹配/情形/默认` |
| 异常 | `尝试/捕获/最终`、`抛出`、可捕获内置错误与系统错误 |
| 模块 | `导入`、`从…导入…`、`导出`；内置模块 + 自己写的 `.ql` 模块 |
| 字符串 | 插值 `${...}`、多行 `"""`、切片、二十多个方法 |
| 标准库 | 数学、时间、随机、文件、JSON、系统、字符串、终端颜色 |
| 其他 | 管道 `|>`、调试命令 `ast` / `tokens`、彩色错误提示与调用栈 |

**中英双语关键字**：`让`/`let`、`函数`/`fn`、`如果`/`if`、`遍历`/`for`……
两种写法完全等价，可以混着写。

---

## 目录结构

```
AI-24h/
├── qiuli.py              # 命令行入口（run / repl / check / ast / tokens / test / new）
├── qiuli.bat             # Windows 双击启动 / 拖拽运行
├── install.ps1           # 可选：把 qiuli 加入 PATH
│
├── src/                  # 解释器实现（纯 Python，零依赖）
│   ├── lexer.py          #   词法分析：中英双关键字、字符串插值
│   ├── parser.py         #   语法分析：递归下降 → AST
│   ├── ast_nodes.py      #   AST 节点定义
│   ├── interpreter.py    #   树遍历执行器
│   ├── environment.py    #   作用域与常量保护
│   ├── objects.py        #   运行时对象（函数、类、实例、模块…）
│   ├── builtins.py       #   内置函数、类型方法、内置模块
│   ├── errors.py         #   带源码定位的彩色错误
│   └── repl.py           #   交互式环境
│
├── stdlib/               # 用 Qiuli 自己写的库
│   └── 数据结构.ql       #   栈、队列、优先队列、链表、二叉搜索树
│
├── examples/             # 15 个示例：从 Hello World 到井字棋、曼德勃罗集
├── tests/                # 测试套件（python qiuli.py test）
├── docs/                 # 教程、语言规范、标准库手册
└── editors/vscode/       # VS Code 语法高亮插件
```

---

## 命令行

```
qiuli <文件.ql> [参数...]      运行脚本（参数在脚本里用 参数 读取）
qiuli run <文件.ql> [参数...]  同上
qiuli repl                     交互式环境（不带参数时默认进入）
qiuli check <文件.ql>          语法检查
qiuli ast <文件.ql>            打印语法树（调试解释器用）
qiuli tokens <文件.ql>         打印词法单元
qiuli test [过滤词]            运行测试套件
qiuli 示例                     列出自带示例（可直接用名字运行）
qiuli new <名字>               用模板新建一个脚本
qiuli version / help

选项：--no-color（关闭彩色）  --time（显示耗时）  --debug（显示完整错误栈）
```

---

## 图标（Windows）

`qiuli.ico` 是自带的 QL 图标（深色圆角底 + 绿色发光字母，含 16/32/48/64/128/256 六种尺寸）。
想微调配色或重新生成：

```bash
python tools/make_icon.py      # 需要 Pillow：pip install pillow
```

Windows 不允许 `.bat` 文件自带图标，所以用快捷方式实现：

**双击 `设置图标.bat`**（或右键 `设置图标.ps1` → 使用 PowerShell 运行），
它会在项目目录里建好两个带图标的快捷方式：

```
Qiuli.lnk          双击进交互环境（REPL）
Qiuli 管理员.lnk    双击进管理员通道
```

想让所有 `.ql` 文件也显示这个图标（并关联成双击运行）：

```powershell
powershell -ExecutionPolicy Bypass -File .\设置图标.ps1 -QlAssoc
```

---

## 管理员通道

想改命令、加命令、封命令，都在这里：

```bash
qiuli admin                      # 进入交互式管理通道（提示符 admin> ）
qiuli admin 命令                 # 看看现在有哪些命令
qiuli admin 别名 ls 示例          # 给「示例」起个别名 ls  → 以后 qiuli ls 就能用
qiuli admin 删除别名 ls
qiuli admin 注册 工具 my.ql       # 把任意脚本注册成子命令 → qiuli 工具
qiuli admin 注销 工具
qiuli admin 禁用 命令             # 禁用某个内置命令（别名也会一起失效）
qiuli admin 启用 命令
qiuli admin 配置                 # 查看全局设置
qiuli admin 配置 彩色 假          # 关掉彩色输出
qiuli admin 配置 递归上限 2000    # 调高递归上限
qiuli admin 口令 1234            # 给管理通道加口令（不带参数＝清除）
qiuli admin 重置                 # 恢复出厂设置
```

交互式通道里直接敲中文指令（不用写 `admin` 前缀）：

```
admin> 命令
admin> 别名 ls 示例
admin> 注册 工具 my.ql 这是个好用的工具
admin> 配置 彩色 假
admin> 退出
```

设置项有三个：`彩色`、`递归上限`、`自动找示例`（找不到文件时是否去 `examples/` 里找）。

配置保存在 **`C:\Users\你的用户名\.qiuli\config.json`**（用户目录，换个项目也生效）。

---

## 学习路径

1. **`docs/入门教程.md`** —— 十二课，从零写到小项目，边读边敲
2. **`docs/语言规范.md`** —— 完整语法参考，遇到细节来查
3. **`docs/标准库.md`** —— 内置函数与模块速查表
4. **`examples/`** —— 14 个可运行的示例，覆盖各个主题

---

## 编辑器支持

VS Code：把 `editors/vscode/` 整个目录复制到
`%USERPROFILE%\.vscode\extensions\qiuli-language\`，重启 VS Code，
`.ql` 文件就有语法高亮、括号匹配、注释切换了。

---

## 性能与边界

Qiuli 是**树遍历解释器**（没有字节码、没有 JIT），定位是教学、脚本与原型。

- 实测：约 **30 万次循环迭代 / 秒**（10 万次累加约 0.3 秒）
- 适合：学习编程、写小工具、处理文本与文件、做算法练习
- 不适合：密集数值计算、实时系统

设计上的几个决定（都在文档里写明了原因）：

- 单行注释用 `#`；`//` 留给整除运算符
- 只有 `空` 和 `假` 是假值，`0` 和 `""` 都是真
- 一行写多条语句用 `;` 分隔；同一行紧挨着写的语句会自动补分号
- 字符串插值 `${...}` 里若要用下标，用单引号：`${字典['键']}`

---

## 版本

**Qiuli 1.0.0** —— 词法、语法、解释器、标准库、模块系统、REPL、
测试套件、示例、文档、编辑器支持，全部齐备。

```
python qiuli.py version
```
