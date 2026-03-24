"""Build system-prompt catalog (name + description only) for configured skills."""

from __future__ import annotations

import logging

from agentlab.storage.store import Store

logger = logging.getLogger(__name__)


def build_skill_catalog_suffix(store: Store, skill_ids: list[str]) -> str:
    """Return markdown block listing skills by id with name and description only."""
    if not skill_ids:
        return ""

    lines: list[str] = []
    for sid in skill_ids:
        try:
            name, desc = store.load_skill_name_description(sid)
            lines.append(f"- `{sid}`: **{name}** — {desc}")
        except FileNotFoundError:
            lines.append(f"- `{sid}`: _(skill not found on disk)_")
            logger.warning("Skill id %r missing on disk", sid)
        except Exception as exc:
            lines.append(f"- `{sid}`: _(error loading: {exc})_")
            logger.warning("Failed to load skill %r: %s", sid, exc)

    return (
        "\n\n## Available skills\n\n"
        "You may load full instructions for a skill using the `load_skill` tool with "
        "`skill_id`. Only the summaries below are pre-loaded; use progressive disclosure "
        "when you need the full SKILL.md body.\n\n"
        + "\n".join(lines)
    )
