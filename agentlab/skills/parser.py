"""Parse SKILL.md with optional YAML frontmatter (--- ... ---)."""

from __future__ import annotations

from typing import Any

import yaml

_FRONTMATTER_SEP = "---"


def parse_skill_md(text: str) -> tuple[dict[str, Any], str]:
    """Split frontmatter and body. Returns (meta_dict, body). Meta may be empty."""
    stripped = text.lstrip()
    if not stripped.startswith(_FRONTMATTER_SEP):
        return {}, text

    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_SEP:
        return {}, text

    end = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == _FRONTMATTER_SEP:
            end = i
            break
    if end < 0:
        return {}, text

    fm_block = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :])
    try:
        meta = yaml.safe_load(fm_block) or {}
    except yaml.YAMLError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, body


def skill_instruction_body(raw_file: str) -> str:
    """Return markdown body after frontmatter; if empty, return full text."""
    meta, body = parse_skill_md(raw_file)
    out = body.strip()
    return out if out else raw_file.strip()


def meta_name_description(meta: dict[str, Any]) -> tuple[str, str]:
    """Extract name and description from frontmatter dict."""
    name = str(meta.get("name") or "").strip()
    desc = str(meta.get("description") or "").strip()
    return name, desc
