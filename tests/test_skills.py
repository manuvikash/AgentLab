"""Tests for SKILL.md parsing, store, load_skill tool, and trace enrichment."""

from __future__ import annotations

import pytest

from agentlab.components.tools.load_skill_tool import LoadSkillTool
from agentlab.core.component import ToolResult
from agentlab.models.schemas import SkillDocument
from agentlab.skills.parser import parse_skill_md, skill_instruction_body
from agentlab.skills.trace import enrich_tool_call_record
from agentlab.storage.store import Store


def test_parse_skill_md_with_frontmatter() -> None:
    text = """---
name: My Skill
description: Does a thing
---

# Instructions

Run **this** first.
"""
    meta, body = parse_skill_md(text)
    assert meta.get("name") == "My Skill"
    assert meta.get("description") == "Does a thing"
    assert "Run **this** first." in body


def test_parse_skill_md_no_frontmatter() -> None:
    text = "Just prose\n\nno yaml."
    meta, body = parse_skill_md(text)
    assert meta == {}
    assert "Just prose" in body


def test_skill_instruction_body_prefers_markdown_body() -> None:
    raw = "---\nname: X\ndescription: Y\n---\n\nBody only.\n"
    assert skill_instruction_body(raw) == "Body only."


def test_store_skill_roundtrip(tmp_path) -> None:
    store = Store(root=tmp_path)
    doc = SkillDocument(
        id="demo_skill",
        name="Demo",
        description="A demo skill.",
        body="Step one.\nStep two.",
    )
    store.save_skill_document(doc)
    loaded = store.load_skill_document("demo_skill")
    assert loaded.id == "demo_skill"
    assert loaded.name == "Demo"
    assert loaded.description == "A demo skill."
    assert "Step one." in loaded.body
    name, desc = store.load_skill_name_description("demo_skill")
    assert name == "Demo"
    assert desc == "A demo skill."
    instr = store.skill_instruction_for_tool("demo_skill")
    assert "Step one." in instr
    assert "Demo" not in instr or "Step" in instr


@pytest.mark.asyncio
async def test_load_skill_tool_allowlist(tmp_path) -> None:
    store = Store(root=tmp_path)
    store.save_skill_document(
        SkillDocument(
            id="allowed",
            name="Allowed",
            description="ok",
            body="secret instructions",
        )
    )
    tool = LoadSkillTool(store=store, allowed_skill_ids=["allowed"])
    out = await tool.execute(sandbox=None, skill_id="allowed")
    assert isinstance(out, ToolResult)
    assert out.success
    assert "secret instructions" in out.output

    denied = await tool.execute(sandbox=None, skill_id="other")
    assert "not enabled" in denied.output.lower()


@pytest.mark.asyncio
async def test_load_skill_requires_store() -> None:
    tool = LoadSkillTool(store=None, allowed_skill_ids=["x"])
    out = await tool.execute(sandbox=None, skill_id="x")
    assert "not configured" in out.output.lower()


def test_enrich_tool_call_record_load_skill(tmp_path) -> None:
    store = Store(root=tmp_path)
    store.save_skill_document(
        SkillDocument(
            id="s1",
            name="Named Skill",
            description="d",
            body="b",
        )
    )
    rec = enrich_tool_call_record(
        "load_skill",
        {"skill_id": "s1"},
        "body text",
        store=store,
    )
    assert rec.tool == "load_skill"
    assert rec.skill_id == "s1"
    assert rec.skill_name == "Named Skill"


def test_skill_file_tree_and_read_bundle(tmp_path) -> None:
    store = Store(root=tmp_path)
    skill_dir = tmp_path / "skills" / "my_skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: X\ndescription: Y\n---\n\n", encoding="utf-8"
    )
    agents = skill_dir / "agents"
    agents.mkdir()
    (agents / "grader.md").write_text("grade", encoding="utf-8")

    tree = store.skill_file_tree("my_skill")
    assert tree["kind"] == "dir"
    names = {c["name"] for c in tree["children"]}
    assert "SKILL.md" in names
    assert "agents" in names

    assert store.read_skill_bundle_file("my_skill", "agents/grader.md") == "grade"


def test_read_skill_bundle_rejects_traversal(tmp_path) -> None:
    store = Store(root=tmp_path)
    skill_dir = tmp_path / "skills" / "my_skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: X\ndescription: Y\n---\n", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(ValueError):
        store.read_skill_bundle_file("my_skill", "../outside.txt")


def test_enrich_tool_call_record_other_tool_no_skill_fields(tmp_path) -> None:
    store = Store(root=tmp_path)
    rec = enrich_tool_call_record(
        "shell",
        {"command": "ls"},
        "out",
        store=store,
    )
    assert rec.skill_id is None
    assert rec.skill_name is None
