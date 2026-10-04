# -*- coding: utf-8 -*-
# ============================================================
# 生成网站图标 favicon（2026-10-03 首次：小猫照片；2026-10-04 改为 SVG 源）
#   源图：user_upload/red-blue.svg（512×512，透明底，红/蓝渐变双圆）
#   产物（写入仓库根目录，随部署上线）：
#     favicon.svg            直接复制源 SVG（现代浏览器首选，矢量无损）
#     favicon.ico            多尺寸 16/32/48（保留透明）
#     favicon-16x16.png      透明
#     favicon-32x32.png      透明
#     apple-touch-icon.png   180×180，压纯白底（iOS 对透明会填黑）
#   口径：SVG → rsvg-convert 光栅化为 512 母版（透明）
#         → 按 alpha 通道裁掉透明留白 → 留 ~6% 内边距 → 正方形画布 → Lanczos 缩放
#   依赖：rsvg-convert（librsvg）+ Pillow。改图后重跑本脚本即可。
# ============================================================
import os, shutil, subprocess, sys, tempfile
from PIL import Image

REPO = os.path.dirname(os.path.abspath(__file__))
SVG = os.path.join(REPO, "user_upload", "red-blue.svg")


def find_rsvg():
    p = shutil.which("rsvg-convert")
    if p:
        return p
    for c in [
        os.path.expanduser("~/Library/Application Support/TRAE SOLO/ModularData/ai-agent/vm/tools/bin/rsvg-convert"),
        "/opt/homebrew/bin/rsvg-convert",
        "/usr/local/bin/rsvg-convert",
    ]:
        if os.path.exists(c):
            return c
    return None


rsvg = find_rsvg()
if not rsvg:
    sys.exit("找不到 rsvg-convert（librsvg）。请先安装（macOS: brew install librsvg）后重跑。")

master_path = os.path.join(tempfile.gettempdir(), "red-blue-512.png")
subprocess.run([rsvg, "-w", "512", "-h", "512", "-o", master_path, SVG], check=True)
print("光栅化母版:", master_path)

# 1) 复制源 SVG 作为 favicon.svg（矢量首选，现代浏览器）
shutil.copyfile(SVG, os.path.join(REPO, "favicon.svg"))
print("写出 favicon.svg")

im = Image.open(master_path).convert("RGBA")
print("母版:", im.size, im.mode)

# 2) 按 alpha 通道裁掉透明留白
bbox = im.getchannel("A").getbbox()
content = im.crop(bbox)
w, h = content.size
print("内容 bbox:", bbox)

# 3) 放到正方形画布并留 ~6% 内边距（避免贴边）
side = max(w, h)
pad = int(round(side * 0.06))
canvas_side = side + pad * 2
canvas = Image.new("RGBA", (canvas_side, canvas_side), (255, 255, 255, 0))
canvas.paste(content, ((canvas_side - w) // 2, (canvas_side - h) // 2), content)


def save_png(size, name, flatten=None):
    img = canvas.resize((size, size), Image.LANCZOS)
    if flatten is not None:
        bg = Image.new("RGBA", (size, size), flatten)
        bg.alpha_composite(img)
        img = bg.convert("RGB")
    img.save(os.path.join(REPO, name))
    print("  写出", name, img.size, img.mode)


save_png(16, "favicon-16x16.png")
save_png(32, "favicon-32x32.png")
save_png(180, "apple-touch-icon.png", flatten=(255, 255, 255, 255))

# 4) 多尺寸 ico（浏览器默认请求 /favicon.ico）
canvas.save(os.path.join(REPO, "favicon.ico"), format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
print("  写出 favicon.ico (16/32/48)")
print("完成")
