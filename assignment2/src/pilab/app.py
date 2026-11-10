"""Composition root kept stable while coursework modules are integrated."""

from dataclasses import dataclass
from pathlib import Path

from pilab_support.llm import LiteLLMBackend

from pilab.core import Agent
from pilab.tools import BashTool, ReadTool, WriteTool


@dataclass(frozen=True, slots=True)
class AppConfig:
    cwd: Path
    model: str
    api_key: str | None = None
    api_base: str | None = None
    provider: str | None = None
    session: Path | None = None
    skills: tuple[str, ...] = ()
    context_limit: int = 32000
    output_reserve: int = 4000
    compact_at: int = 20000


def create_agent(config: AppConfig) -> Agent:
    cwd = config.cwd.resolve()
    if not cwd.is_dir():
        raise ValueError(f"Workspace is not a directory: {cwd}")
    return Agent(
        backend=LiteLLMBackend(
            config.model,
            api_key=config.api_key,
            api_base=config.api_base,
            provider=config.provider,
            max_tokens=config.output_reserve,
        ),
        system_prompt=(
            "You are a coding assistant. Read requirements and source before editing. "
            "Follow read's next_offset until you have the complete original file. "
            "Use write with complete replacement content to make changes and bash to run checks. "
            "Preserve input data. "
            "Base your answer on tool results; a successful command alone does not prove correctness. "
            f"The current working directory is {cwd}."
        ),
        tools=[ReadTool(cwd), WriteTool(cwd), BashTool(cwd)],
        workspace=cwd,
        session=config.session,
        skills=config.skills,
        context_limit=config.context_limit,
        output_reserve=config.output_reserve,
        compact_at=config.compact_at,
    )
