"""Project instructions, on-demand Skills, and inspectable input estimates."""

import json
from pathlib import Path

import yaml
from pilab_support.llm.litellm_backend import to_chat_completion_messages
from pilab_support.messages import Message, UserMessage


def skill_metadata(path: Path) -> dict[str, str]:
    """Read YAML frontmatter without loading an unselected Skill's body."""
    with path.open(encoding="utf-8-sig") as stream:
        if stream.readline().strip() != "---":
            return {}
        lines = []
        for line in stream:
            if line.strip() == "---":
                break
            lines.append(line)
        else:
            raise ValueError(f"Unterminated Skill frontmatter: {path}")
    try:
        metadata = yaml.safe_load("".join(lines))
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid Skill frontmatter: {path}") from error
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise ValueError(f"Skill frontmatter must be a mapping: {path}")
    result = {}
    for key in ("name", "description"):
        if key in metadata:
            if not isinstance(metadata[key], str) or not metadata[key].strip():
                raise ValueError(f"Skill {key} must be a nonempty string: {path}")
            result[key] = metadata[key].strip()
    return result


def project_instructions(workspace: Path, selected: list[str]) -> str:
    parts = []
    rules = workspace / "AGENTS.md"
    if rules.is_file():
        parts.append(f"Project rules ({rules.name}):\n{rules.read_text(encoding='utf-8')}")
    skills: dict[str, tuple[Path, str]] = {}
    for path in sorted((workspace / ".agents" / "skills").glob("*/SKILL.md")):
        metadata = skill_metadata(path)
        name = metadata.get("name", path.parent.name)
        if name in skills:
            raise ValueError(f"Duplicate Skill name: {name}")
        skills[name] = (path, metadata.get("description", ""))
    if skills:
        parts.append("Available Skills (metadata only):\n" + "\n".join(
            f"- {name}: {description}; path={path.relative_to(workspace)}"
            for name, (path, description) in skills.items()
        ))
    for name in dict.fromkeys(selected):
        if name not in skills:
            raise ValueError(f"Unknown Skill: {name}")
        path, _ = skills[name]
        parts.append(
            f"Selected Skill {name} ({path.relative_to(workspace)}):\n"
            + path.read_text(encoding="utf-8")
            + f"\nResolve its attachments relative to {path.parent.relative_to(workspace)}. "
            "Read attachment contents only when needed."
        )
    return "\n\n".join(parts)


def inspect_request(
    messages: list[Message], definitions: list[dict], system_prompt: str, input_budget: int
) -> dict:
    """Estimate complete request input without paid counting calls.

    Use one estimated token per three UTF-8 bytes, plus framing overhead.
    This is a labeled heuristic, not provider usage or an exact tokenizer.
    Include the wire messages and all exposed tool definitions.
    """
    request = {"messages": to_chat_completion_messages(messages, system_prompt)}
    if definitions:
        request.update(tools=definitions, tool_choice="auto")
    serialized = json.dumps(request, ensure_ascii=False)
    count = (len(serialized.encode("utf-8")) + 2) // 3 + 32 * (len(messages) + len(definitions) + 1)
    return {
        "method": "estimated tokens: UTF-8 bytes / 3 plus framing (heuristic, not provider usage)",
        "input_tokens": count,
        "input_budget": input_budget,
        "fits": count <= input_budget,
        "request": request,
    }


def interaction_groups(messages: list[Message]) -> list[list[Message]]:
    """Group each user request with all of its assistant turns and tool results."""
    groups: list[list[Message]] = []
    for message in messages:
        if isinstance(message, UserMessage) or not groups:
            groups.append([message])
        else:
            groups[-1].append(message)
    return groups
