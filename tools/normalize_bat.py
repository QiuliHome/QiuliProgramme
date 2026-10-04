"""把项目里的 .bat / .cmd 规范化成 Windows 能正确解析的形式

cmd.exe 的两条硬性要求（踩过坑）：
  1. 行尾必须是 CRLF —— 只有 LF 时，每行开头几个字符会被吃掉，
     报出 "某半个单词 不是内部或外部命令"
  2. 含中文的批处理要用 GBK（ANSI）编码 —— 用 UTF-8 会让中文文件名乱码

用法：python tools/normalize_bat.py [目录]
"""

import os
import sys

TARGETS = ("qiuli.bat", "qiuli.cmd", "管理员通道.bat", "设置图标.bat")


def normalize(path):
    raw = open(path, "rb").read()
    changed = []

    # ---- 解码 ----
    text = None
    for enc in ("utf-8-sig", "gbk"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")

    # ---- 统一行尾为 CRLF ----
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    needs_crlf = b"\r\n" not in raw
    text = text.replace("\n", "\r\n")
    if needs_crlf:
        changed.append("行尾 LF → CRLF")

    # ---- 选择编码：含非 ASCII 就用 GBK ----
    ascii_only = all(ord(c) < 128 for c in text)
    enc = "ascii" if ascii_only else "gbk"
    new_raw = text.encode(enc)
    if new_raw != raw:
        changed.append("编码 → %s" % enc)

    if new_raw != raw:
        with open(path, "wb") as f:
            f.write(new_raw)
    return changed


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    done = 0
    for name in TARGETS:
        p = os.path.join(root, name)
        if not os.path.exists(p):
            continue
        ch = normalize(p)
        if ch:
            print("  修复 %-18s %s" % (name, "，".join(ch)))
            done += 1
        else:
            print("  正常 %-18s（无需改动）" % name)
    print("\n共处理 %d 个文件" % done)


if __name__ == "__main__":
    main()
