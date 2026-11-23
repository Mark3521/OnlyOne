#!/usr/bin/env python3
"""Validate OnlyOne icon resources without third-party Python dependencies."""
from __future__ import annotations

import argparse
import collections
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "app/src/main/res"
ANDROID_NS = "{http://schemas.android.com/apk/res/android}"


def png_info(path: Path):
    data = path.read_bytes()
    if len(data) < 26 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是有效 PNG 文件")
    width, height = struct.unpack(">II", data[16:24])
    color_type = data[25]
    has_alpha = color_type in (4, 6) or (color_type == 3 and b"tRNS" in data)
    return width, height, color_type, has_alpha


def parse_xml(path: Path, errors: list[str]):
    try:
        return ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        errors.append(f"XML 无法解析：{path.relative_to(ROOT)}：{exc}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 OnlyOne 图标资源完整性")
    parser.add_argument("--quiet", action="store_true", help="仅输出错误和最终统计")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    adaptive_dir = RES / "drawable-anydpi-v26"
    png_dir = RES / "drawable-xxxhdpi"
    appfilter_path = RES / "xml/appfilter.xml"
    drawable_path = RES / "xml/drawable.xml"

    adaptive_files = sorted(adaptive_dir.glob("*.xml"))
    adaptive_names = {p.stem for p in adaptive_files}
    png_files = sorted(png_dir.glob("*.png"))

    drawable_resources: set[str] = set()
    for folder in RES.glob("drawable*"):
        if folder.is_dir():
            for p in folder.iterdir():
                if p.is_file() and p.suffix.lower() in {".png", ".xml", ".webp", ".jpg", ".jpeg"}:
                    drawable_resources.add(p.stem)

    color_resources: set[str] = set()
    for values_dir in RES.glob("values*"):
        if values_dir.is_dir():
            for xml_file in values_dir.glob("*.xml"):
                root = parse_xml(xml_file, errors)
                if root is not None:
                    for element in root:
                        if element.tag in {"color", "selector"} and element.get("name"):
                            color_resources.add(element.get("name"))

    appfilter = parse_xml(appfilter_path, errors)
    drawable_list = parse_xml(drawable_path, errors)
    components: list[str] = []
    if appfilter is not None:
        for item in appfilter.findall("item"):
            drawable = item.get("drawable")
            component = item.get("component")
            if drawable and drawable not in adaptive_names:
                errors.append(f"appfilter 引用了不存在的 Adaptive Icon：{drawable}")
            if component:
                components.append(component)
                if not (component.startswith("ComponentInfo{") and component.endswith("}")):
                    errors.append(f"Activity component 格式异常：{component}")

    list_drawables: list[str] = []
    if drawable_list is not None:
        for item in drawable_list.findall("item"):
            drawable = item.get("drawable")
            if drawable:
                list_drawables.append(drawable)
                if drawable not in adaptive_names:
                    errors.append(f"drawable.xml 引用了不存在的 Adaptive Icon：{drawable}")

    for name, count in collections.Counter(list_drawables).items():
        if count > 1:
            warnings.append(f"drawable.xml 中存在重复展示项：{name}（{count} 次；需人工确认）")
    for component, count in collections.Counter(components).items():
        if count > 1:
            warnings.append(f"appfilter.xml 中存在重复 Activity 映射：{component}（{count} 次；保留原项目数据）")

    for name in sorted(adaptive_names - set(list_drawables)):
        warnings.append(f"Adaptive Icon 未加入 drawable.xml 展示列表：{name}")
    for name in sorted(set(list_drawables) - adaptive_names):
        errors.append(f"图标列表引用缺少 Adaptive Icon：{name}")

    for xml_file in adaptive_files:
        root = parse_xml(xml_file, errors)
        if root is None:
            continue
        if root.tag != "adaptive-icon":
            errors.append(f"Adaptive Icon 根节点不正确：{xml_file.name}")
        child_tags = {node.tag for node in root}
        if "foreground" not in child_tags:
            errors.append(f"Adaptive Icon 缺少 foreground：{xml_file.name}")
        if "background" not in child_tags:
            errors.append(f"Adaptive Icon 缺少 background：{xml_file.name}")
        for node in root.iter():
            value = node.get(ANDROID_NS + "drawable")
            if not value or not value.startswith("@"):
                continue
            if value.startswith("@drawable/"):
                ref = value.split("/", 1)[1]
                if ref not in drawable_resources:
                    errors.append(f"{xml_file.name} 引用了不存在的 drawable：{value}")
            elif value.startswith("@color/"):
                ref = value.split("/", 1)[1]
                if ref not in color_resources:
                    errors.append(f"{xml_file.name} 引用了不存在的 color：{value}")

    png_stats = collections.Counter()
    for png in png_files:
        try:
            width, height, color_type, has_alpha = png_info(png)
            png_stats[(width, height)] += 1
            if (width, height) != (432, 432):
                warnings.append(f"既有 PNG 尺寸不是 432×432：{png.name}（{width}×{height}）")
            if color_type != 6:
                warnings.append(f"既有 PNG 不是 RGBA 色彩类型：{png.name}（PNG color type {color_type}）")
            if not has_alpha:
                warnings.append(f"既有 PNG 未检测到透明通道：{png.name}")
        except (OSError, ValueError, struct.error) as exc:
            errors.append(f"PNG 无法读取：{png.name}：{exc}")

    if not args.quiet:
        print(f"Adaptive Icon：{len(adaptive_files)}")
        print(f"xxxhdpi PNG：{len(png_files)}")
        print(f"appfilter Activity 映射：{len(components)}")
        print(f"drawable.xml 展示项：{len(list_drawables)}")
        print(f"PNG 尺寸分布：{dict(png_stats)}")
    for warning in warnings:
        print(f"[WARN] {warning}")
    for error in errors:
        print(f"[ERROR] {error}")
    print(f"检查完成：{len(errors)} 个错误，{len(warnings)} 个警告。")
    if errors:
        print("资源检查失败。请先修复错误后再编译。")
        return 1
    print("资源检查通过。警告为原项目中发现的历史资源问题，不会阻断构建。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
