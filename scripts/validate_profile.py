#!/usr/bin/env python3
"""Validate the profile README and its local SVG assets using only stdlib."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ERRORS: list[str] = []


def error(message: str) -> None:
    ERRORS.append(message)
    print(f"ERROR: {message}")


def validate_focus_map_text_bounds(svg_path: Path) -> None:
    """Conservatively check centered labels fit inside their map circles."""
    try:
        root = ET.parse(svg_path).getroot()
    except (ET.ParseError, OSError):
        return  # The general SVG parser below reports the underlying error.

    circles: list[tuple[float, float, float]] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "circle":
            continue
        try:
            circles.append(
                (float(element.attrib["cx"]), float(element.attrib["cy"]), float(element.attrib["r"]))
            )
        except (KeyError, ValueError):
            continue

    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "text" or element.attrib.get("text-anchor") != "middle":
            continue
        try:
            x = float(element.attrib["x"])
            y = float(element.attrib["y"])
            font_size = float(element.attrib.get("font-size", "16"))
        except (KeyError, ValueError):
            continue

        containing = [
            radius for cx, cy, radius in circles
            if abs(cx - x) < 0.5 and abs(y - cy) <= radius
        ]
        if not containing:
            continue

        label = "".join(element.itertext()).strip()
        if not label:
            continue
        # SVG uses a monospace font for the focus map. This estimate adds a
        # safety margin without requiring third-party font or rendering tools.
        estimated_width = len(label) * font_size * 0.62
        available_width = 2 * min(containing) - 8
        if estimated_width > available_width:
            error(
                f"{svg_path.relative_to(ROOT)}: centered label {label!r} may overflow "
                f"its circle (estimated {estimated_width:.1f}px > {available_width:.1f}px)."
            )


def main() -> int:
    if not README.is_file():
        error("README.md is missing.")
        return 1

    readme = README.read_text(encoding="utf-8")

    for match in re.finditer(r"<img\b[^>]*>", readme, flags=re.IGNORECASE | re.DOTALL):
        tag = match.group(0)
        line = readme.count("\n", 0, match.start()) + 1
        alt = re.search(r"""\balt\s*=\s*(["'])(.*?)\1""", tag, flags=re.IGNORECASE | re.DOTALL)
        if not alt or not alt.group(2).strip():
            error(f"README.md:{line}: <img> is missing a meaningful alt attribute.")

        src = re.search(r"""\bsrc\s*=\s*(["'])(.*?)\1""", tag, flags=re.IGNORECASE | re.DOTALL)
        if src and not re.match(r"^(?:https?:)?//", src.group(2)):
            target = (ROOT / src.group(2).split("#", 1)[0]).resolve()
            if not target.is_relative_to(ROOT.resolve()) or not target.is_file():
                error(f"README.md:{line}: local image does not exist: {src.group(2)}")

    for match in re.finditer(r"""\bsrcset\s*=\s*(["'])(.*?)\1""", readme, flags=re.IGNORECASE | re.DOTALL):
        line = readme.count("\n", 0, match.start()) + 1
        for candidate in match.group(2).split(","):
            url = candidate.strip().split()[0] if candidate.strip() else ""
            if not url or re.match(r"^(?:https?:)?//", url):
                continue
            target = (ROOT / url.split("#", 1)[0]).resolve()
            if not target.is_relative_to(ROOT.resolve()) or not target.is_file():
                error(f"README.md:{line}: local srcset asset does not exist: {url}")

    asset_dir = ROOT / "assets"
    svg_files = sorted(asset_dir.glob("*.svg"))
    for svg in svg_files:
        try:
            root = ET.parse(svg).getroot()
        except (ET.ParseError, OSError) as exc:
            error(f"{svg.relative_to(ROOT)}: invalid SVG/XML: {exc}")
            continue
        if not root.tag.endswith("svg"):
            error(f"{svg.relative_to(ROOT)}: root element is not <svg>.")
        if svg.name == "focus-map.svg":
            validate_focus_map_text_bounds(svg)
        content = svg.read_text(encoding="utf-8")
        if re.search(r"<span\b", content, flags=re.IGNORECASE):
            error(f"{svg.relative_to(ROOT)}: HTML <span> is invalid in SVG; use <tspan>.")
        if svg.relative_to(ROOT).as_posix() not in readme:
            error(f"{svg.relative_to(ROOT)}: SVG is not referenced by README.md.")

    if ERRORS:
        print(f"\nValidation failed with {len(ERRORS)} error(s).")
        return 1

    print(f"Validation passed: README image references, alt attributes, and {len(svg_files)} SVG assets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
