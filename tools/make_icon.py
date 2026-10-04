"""生成 Qiuli 的图标：绿色科技风「QL」

产出：
    qiuli.ico            多尺寸 Windows 图标（16/32/48/64/128/256）
    assets/icon/qiuli_256.png   预览图（大图）
    assets/icon/qiuli_128.png
    assets/icon/qiuli_48.png

设计：
    深色圆角方块 + 淡绿网格 + 四角取景框 + 底部光带 + 发光字母 QL
    大尺寸带细节，16/32/48 用简化版（去掉网格，字母加粗）保证小图清晰

用法：python tools/make_icon.py
"""

import os
import struct

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ICO = os.path.join(HERE, "qiuli.ico")
OUT_DIR = os.path.join(HERE, "assets", "icon")

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\CascadiaCode.ttf",
    r"C:\Windows\Fonts\consolab.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
]

# 配色
BG_TOP = (5, 12, 16)
BG_BOTTOM = (9, 30, 30)
GREEN = (46, 232, 138)
GREEN_LIGHT = (168, 255, 212)
GRID = (46, 232, 138, 22)
FRAME = (74, 240, 160, 165)

SS = 4          # 超采样倍率


def load_font(px):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, px)
            except Exception:
                continue
    return ImageFont.load_default()


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1],
                                        radius=radius, fill=255)
    return m


def vertical_gradient(size, top, bottom):
    g = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(g)
    for y in range(size):
        t = y / max(size - 1, 1)
        d.line([(0, y), (size, y)],
               fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    return g


def letter_mask(size, text, font, tracking=0, dy=0):
    """把文字渲染成一张 L 遮罩，支持字距调整"""
    tmp = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(tmp)
    # 逐字排版，手动控制字距
    widths = []
    for ch in text:
        bb = d.textbbox((0, 0), ch, font=font)
        widths.append((bb, ch))
    total = sum(bb[2] - bb[0] for bb, _ in widths) + tracking * (len(text) - 1)
    x = (size - total) / 2
    max_h = max(bb[3] - bb[1] for bb, _ in widths)
    for bb, ch in widths:
        w = bb[2] - bb[0]
        y = (size - max_h) / 2 - bb[1] + dy
        d.text((x - bb[0], y), ch, font=font, fill=255)
        x += w + tracking
    return tmp


def render(size, detail=True):
    """渲染一张 size×size 的图标（内部按 SS 倍超采样）"""
    S = size * SS
    R = int(S * 0.225)                      # 圆角半径

    # ---- 背景 ----
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    mask = rounded_mask(S, R)
    img.paste(vertical_gradient(S, BG_TOP, BG_BOTTOM), (0, 0), mask)

    if detail:
        # 网格
        grid = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grid)
        step = max(int(S / 8), 4)
        lw = max(int(S / 340), 1)
        for i in range(step, S, step):
            gd.line([(i, 0), (i, S)], fill=GRID, width=lw)
            gd.line([(0, i), (S, i)], fill=GRID, width=lw)
        grid.putalpha(Image.composite(grid.getchannel("A"),
                                      Image.new("L", (S, S), 0), mask))
        img.alpha_composite(grid)

        # 四角取景框
        fr = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        fd = ImageDraw.Draw(fr)
        off = int(S * 0.13)
        L = int(S * 0.115)
        w = max(int(S / 150), 2)
        for (cx, cy, sx, sy) in ((off, off, 1, 1),
                                 (S - off, S - off, -1, -1)):
            fd.line([(cx, cy + L * sy), (cx, cy)], fill=FRAME, width=w)
            fd.line([(cx, cy), (cx + L * sx, cy)], fill=FRAME, width=w)
        img.alpha_composite(fr)

    # ---- 字母 QL ----
    font = load_font(int(S * (0.40 if detail else 0.46)))
    tracking = -int(S * 0.012)
    tm = letter_mask(S, "QL", font, tracking, dy=int(S * 0.005))

    # 外发光
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    glow.paste(GREEN + (255,), (0, 0), tm)
    glow = glow.filter(ImageFilter.GaussianBlur(S * 0.035))
    img.alpha_composite(glow)
    img.alpha_composite(glow)

    # 字母本体：上亮下深的绿色渐变
    tg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    td = ImageDraw.Draw(tg)
    for y in range(S):
        t = y / S
        c = (int(GREEN_LIGHT[0] + (GREEN[0] - GREEN_LIGHT[0]) * t),
             int(GREEN_LIGHT[1] + (GREEN[1] - GREEN_LIGHT[1]) * t),
             int(GREEN_LIGHT[2] + (GREEN[2] - GREEN_LIGHT[2]) * t), 255)
        td.line([(0, y), (S, y)], fill=c)
    img.paste(tg, (0, 0), tm)

    # 细描边，让字母更利落
    edge = tm.filter(ImageFilter.MaxFilter(3))
    rim = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    rim.paste((10, 40, 30, 160), (0, 0), edge)
    rim.paste((0, 0, 0, 0), (0, 0), tm)
    img.alpha_composite(rim)

    # ---- 外圈描边 ----
    ring = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.rounded_rectangle([1, 1, S - 2, S - 2], radius=R,
                         outline=(70, 220, 150, 90), width=max(int(S / 200), 1))
    img.alpha_composite(ring)

    return img.resize((size, size), Image.LANCZOS)


def write_ico(path, images):
    """手写 ICO 打包，把多张 PNG 塞进同一个 .ico（Vista+ 支持内嵌 PNG）"""
    n = len(images)
    header = struct.pack("<HHH", 0, 1, n)
    entries, blobs = b"", b""
    offset = 6 + 16 * n
    for im in images:
        import io
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        data = buf.getvalue()
        w = 0 if im.width >= 256 else im.width
        h = 0 if im.height >= 256 else im.height
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        blobs += data
    with open(path, "wb") as f:
        f.write(header + entries + blobs)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    big = render(256, detail=True)          # 大图带细节
    mid = render(48, detail=False)          # 小图简化，保证清晰
    tiny = render(32, detail=False)
    mini = render(16, detail=False)

    previews = {
        256: big,
        128: big.resize((128, 128), Image.LANCZOS),
        64: big.resize((64, 64), Image.LANCZOS),
        48: mid,
        32: tiny,
        16: mini,
    }

    write_ico(OUT_ICO, [previews[s] for s in (256, 128, 64, 48, 32, 16)])

    for s in (256, 128, 48):
        previews[s].save(os.path.join(OUT_DIR, "qiuli_%d.png" % s))

    print("已生成图标：")
    print("   %s  (%d 字节)" % (OUT_ICO, os.path.getsize(OUT_ICO)))
    for s in (256, 128, 48):
        p = os.path.join(OUT_DIR, "qiuli_%d.png" % s)
        print("   %s" % p)


if __name__ == "__main__":
    main()
