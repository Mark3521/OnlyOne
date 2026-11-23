#!/usr/bin/env python3
"""Add an Adaptive Icon and register its Android launcher component(s)."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "app/src/main/res"
ANDROID_NS = "http://schemas.android.com/apk/res/android"


def fail(message: str) -> None:
    raise SystemExit(f"[ERROR] {message}")


def png_info(path: Path):
    data = path.read_bytes()
    if len(data) < 26 or data[:8] != b"\x89PNG\r\n\x1a\n":
        fail(f"{path} 不是有效 PNG 文件")
    width, height = struct.unpack(">II", data[16:24])
    color_type = data[25]
    has_alpha = color_type == 6
    if (width, height) != (432, 432):
        fail(f"{path} 尺寸为 {width}×{height}，要求 432×432")
    if color_type != 6 or not has_alpha:
        fail(f"{path} 必须是带透明通道的 RGBA PNG（color type 6）")


def valid_resource_name(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_]*", value))


def expand_activity(package: str, activity: str) -> str:
    activity = activity.strip()
    if activity.startswith("."):
        return package + activity
    if "." not in activity:
        return package + "." + activity
    return activity


def add_appfilter_item(path: Path, component: str, drawable: str, label: str) -> None:
    tree = ET.parse(path)
    root = tree.getroot()
    for item in root.findall("item"):
        if item.get("component") == component:
            fail(f"Activity 已存在于 appfilter.xml：{component}")
    text = path.read_text(encoding="utf-8")
    insertion = (
        f'    <!-- {label} -->\n'
        f'    <item\n'
        f'        component="{component}"\n'
        f'        drawable="{drawable}"/>\n'
    )
    closing = re.search(r"</resources>\s*$", text)
    if not closing:
        fail("appfilter.xml 缺少 resources 结束标签")
    text = text[:closing.start()] + insertion + text[closing.start():]
    path.write_text(text, encoding="utf-8")


def add_drawable_item(path: Path, drawable: str) -> None:
    tree = ET.parse(path)
    root = tree.getroot()
    if drawable in {item.get("drawable") for item in root.findall("item")}:
        fail(f"图标已存在于 drawable.xml：{drawable}")

    text = path.read_text(encoding="utf-8")
    letter = drawable[0].upper()
    category_pattern = re.compile(r'<category\s+title="([^"]+)"\s*/>')
    comment_pattern = re.compile(r'<!--\s*([A-Z]|Special|Dynamic)\s*-->')
    categories = list(category_pattern.finditer(text))
    comments = list(comment_pattern.finditer(text))
    target = next((m for m in categories if m.group(1) == letter), None)
    item_line = f'    <item drawable="{drawable}"/>\n'

    def line_start(position: int) -> int:
        return text.rfind("\n", 0, position) + 1

    if target:
        following = next((m for m in comments if m.start() > target.start()), None)
        end = line_start(following.start()) if following else line_start(text.rfind("</resources>"))
        text = text[:end] + item_line + text[end:]
    else:
        heading = next((m for m in comments if m.group(1) == letter), None)
        category_line = f'    <category title="{letter}" />\n'
        if heading:
            end_of_heading = text.find("\n", heading.end())
            pos = len(text) if end_of_heading < 0 else end_of_heading + 1
            text = text[:pos] + category_line + item_line + text[pos:]
        else:
            later = next((m for m in comments if m.group(1) in {"Special", "Dynamic"} or (len(m.group(1)) == 1 and m.group(1) > letter)), None)
            pos = line_start(later.start()) if later else line_start(text.rfind("</resources>"))
            new_section = f'    <!-- {letter} -->\n' + category_line + item_line
            text = text[:pos] + new_section + text[pos:]
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="从一个图标目录自动添加 OnlyOne 图标")
    parser.add_argument("source", type=Path, help="包含 fg.png、bg.png、config.json 的目录")
    parser.add_argument("--dry-run", action="store_true", help="只检查输入，不写入项目")
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.is_dir():
        fail(f"输入目录不存在：{source}")
    config_path = source / "config.json"
    fg = source / "fg.png"
    bg = source / "bg.png"
    for path in (config_path, fg, bg):
        if not path.is_file():
            fail(f"缺少必要文件：{path.name}")

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        fail(f"config.json 无法读取：{exc}")

    label = str(config.get("name", "")).strip()
    package = str(config.get("package", "")).strip()
    activities = config.get("activities")
    if activities is None:
        activity = config.get("activity")
        activities = [activity] if activity else []
    if not label:
        fail("config.json 必须提供非空 name")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+", package):
        fail("package 格式不正确")
    if not isinstance(activities, list) or not activities or not all(isinstance(x, str) and x.strip() for x in activities):
        fail("请提供 activity 字符串，或非空 activities 字符串数组")

    drawable = str(config.get("drawable", "")).strip()
    if not drawable:
        drawable = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    if not valid_resource_name(drawable):
        fail(f"drawable 名称不符合 Android 资源命名规范：{drawable}")

    png_info(fg)
    png_info(bg)
    adaptive_dir = RES / "drawable-anydpi-v26"
    png_dir = RES / "drawable-xxxhdpi"
    adaptive_xml = adaptive_dir / f"{drawable}.xml"
    target_fg = png_dir / f"{drawable}_fg.png"
    target_bg = png_dir / f"{drawable}_bg.png"
    if adaptive_xml.exists() or target_fg.exists() or target_bg.exists():
        fail(f"目标图标资源已存在：{drawable}")

    components = []
    for raw_activity in activities:
        expanded = expand_activity(package, raw_activity)
        if not expanded.startswith(package + ".") and expanded != package:
            fail(f"Activity 不属于 package {package}：{expanded}")
        components.append(f"ComponentInfo{{{package}/{expanded}}}")

    existing_root = ET.parse(RES / "xml/appfilter.xml").getroot()
    existing_components = {item.get("component") for item in existing_root.findall("item")}
    duplicate_components = existing_components.intersection(components)
    if duplicate_components:
        fail("以下 Activity 已存在：" + ", ".join(sorted(duplicate_components)))
    existing_drawables = {item.get("drawable") for item in ET.parse(RES / "xml/drawable.xml").getroot().findall("item")}
    if drawable in existing_drawables:
        fail(f"drawable.xml 已包含图标：{drawable}")

    adaptive_content = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<adaptive-icon xmlns:android="{ANDROID_NS}">\n'
        f'    <foreground android:drawable="@drawable/{drawable}_fg"/>\n'
        f'    <background android:drawable="@drawable/{drawable}_bg"/>\n'
        '</adaptive-icon>\n'
    )
    if args.dry_run:
        print("[OK] 输入配置和两张 PNG 均符合要求")
        print(f"[PLAN] 新建 {adaptive_xml.relative_to(ROOT)}")
        print(f"[PLAN] 复制 {fg.name} → {target_fg.relative_to(ROOT)}")
        print(f"[PLAN] 复制 {bg.name} → {target_bg.relative_to(ROOT)}")
        for component in components:
            print(f"[PLAN] 注册 Activity：{component}")
        print(f"[PLAN] 更新 drawable.xml：{drawable}")
        return 0

    appfilter_path = RES / "xml/appfilter.xml"
    drawable_path = RES / "xml/drawable.xml"
    appfilter_backup = appfilter_path.read_bytes()
    drawable_backup = drawable_path.read_bytes()
    try:
        shutil.copy2(fg, target_fg)
        shutil.copy2(bg, target_bg)
        adaptive_xml.write_text(adaptive_content, encoding="utf-8")
        for component in components:
            add_appfilter_item(appfilter_path, component, drawable, label)
        add_drawable_item(drawable_path, drawable)
    except Exception:
        appfilter_path.write_bytes(appfilter_backup)
        drawable_path.write_bytes(drawable_backup)
        for path in (target_fg, target_bg, adaptive_xml):
            path.unlink(missing_ok=True)
        raise

    print(f"[OK] 已添加图标：{label} ({drawable})")
    print(f"[OK] 已注册 {len(components)} 个 Activity")
    print("下一步：python tools/validate_icons.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
