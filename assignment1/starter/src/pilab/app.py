"""Composition root kept stable while coursework modules are integrated."""

from dataclasses import dataclass
from pathlib import Path

from pilab_support.llm import LiteLLMBackend

from pilab.core import Agent


@dataclass(frozen=True, slots=True)
class AppConfig:
    cwd: Path
    model: str
    api_key: str | None = None
    api_base: str | None = None
    provider: str | None = None


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
        ),
        system_prompt=(f"You are a coding assistant. The current working directory is {cwd}."),
    )
