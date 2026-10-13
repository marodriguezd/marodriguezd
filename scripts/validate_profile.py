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
