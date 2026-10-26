"""把 GPT Image 2 生成的学术主题配图转成 WebP/PNG 并放进工作台素材目录。

这是**一次性开发工具**，不参与运行、不被任何模块 import、CI 也不执行。
它只被用来说明 `workbench/web/assets/visuals/` 下那批配图是怎么来的。

用法::

    # ANTIGRAVITY_UPLOAD_DIR 指向放原始 PNG 的目录（每次不同，故不作默认值）
    set ANTIGRAVITY_UPLOAD_DIR=C:\\path\\to\\.user_uploaded
    .venv\\Scripts\\python.exe tools\\process_user_images.py

    # 或直接给参数
    .venv\\Scripts\\python.exe tools\\process_user_images.py --src C:\\path\\to\\.user_uploaded

为什么不用写死的路径
--------------------
这里原先写死了两位维护者的本机绝对路径（`C:\\Users\\<用户名>\\...` 与 `D:\\ic-mentor-db\\...`）。
那既把本机用户目录泄进了公开仓库，也违反了本项目「脚本以自身位置解析仓库根目录、
不含硬编码绝对路径」的约定。输入目录改为环境变量/参数传入，输出目录由本文件位置推导。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:  # Pillow 属开发期依赖，清单见 workbench/requirements.txt 末尾注释
    from PIL import Image
except ImportError:  # pragma: no cover - 只在未装开发依赖时触发
    sys.exit("需要 Pillow：py -3.12 -m pip install pillow")

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "workbench" / "web" / "assets" / "visuals"

# 输出名 -> 原始文件名。原始名由上游生成器给出，保持原样以免重复导图时错位。
MAPPING = {
    "hero-academic": "media_1792900650725_3d0401de.png",
    "source-academic": "media_1792900650728_37e48182.png",
    "search-empty": "media_1792900650746_614349e4.png",
    "discipline-explore": "media_1792900650693_0ebf9c3b.png",
    "about-academic": "media_1792900650710_17444c7c.png",
    "records-empty": "media_1792901784317_73388470.png",
}


def source_dir(cli_value: str | None) -> Path:
    """原始图目录：命令行优先，其次环境变量；两者都没有就报错退出。"""
    raw = cli_value or os.environ.get("ANTIGRAVITY_UPLOAD_DIR", "")
    if not raw:
        sys.exit(
            "缺少原始图目录。请用 --src <目录> 或设置环境变量 ANTIGRAVITY_UPLOAD_DIR。\n"
            "（该目录含每次生成都不同的随机名，因此不提供默认值。）"
        )
    path = Path(raw).expanduser()
    if not path.is_dir():
        sys.exit(f"原始图目录不存在或不是目录：{path}")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="把原始配图转成 WebP/PNG 并写入工作台素材目录")
    ap.add_argument("--src", help="原始 PNG 所在目录（也可用环境变量 ANTIGRAVITY_UPLOAD_DIR）")
    ap.add_argument("--out", default=str(OUTPUT_DIR), help=f"输出目录，默认 {OUTPUT_DIR}")
    args = ap.parse_args(argv)

    src = source_dir(args.src)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"原始图：{src}\n输出：  {out}\n")

    missing = 0
    for name, filename in MAPPING.items():
        src_path = src / filename
        if not src_path.is_file():
            print(f"跳过 {name}：缺少 {src_path.name}")
            missing += 1
            continue

        with Image.open(src_path) as image:
            img = image.convert("RGBA") if image.mode != "RGBA" else image.copy()
            print(f"读取 {name}：{img.size}，mode={img.mode}")

            png_dest = out / f"{name}.png"
            img.save(png_dest, format="PNG", optimize=True)

            webp_dest = out / f"{name}.webp"
            img.save(webp_dest, format="WEBP", quality=90, method=6)

            print(f"  -> {png_dest.name} ({png_dest.stat().st_size / 1024:.1f} KB)"
                  f" & {webp_dest.name} ({webp_dest.stat().st_size / 1024:.1f} KB)")

            if name == "hero-academic":
                mobile_w = 640
                mobile_h = int(img.height * (mobile_w / img.width))
                mobile = img.resize((mobile_w, mobile_h), Image.Resampling.LANCZOS)
                mobile_dest = out / "hero-academic-mobile.webp"
                mobile.save(mobile_dest, format="WEBP", quality=88, method=6)
                print(f"  -> {mobile_dest.name} ({mobile_dest.stat().st_size / 1024:.1f} KB)")

    if missing:
        print(f"\n有 {missing} 张原始图缺失，未生成对应输出。")
        return 1
    print("\n全部完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())