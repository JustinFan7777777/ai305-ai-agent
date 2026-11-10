"""Connect the Starter Agent to the supplied command-line runner."""

import argparse
from pathlib import Path

from pilab_support.cli import add_batch_command, create_parser, run_cli

from pilab import __version__
from pilab.app import AppConfig, create_agent


def build_parser() -> argparse.ArgumentParser:
    parser = create_parser(description="PiLab Starter", version=__version__)
    parser.add_argument("--session", type=Path)
    parser.add_argument("--skill", action="append", default=[])
    parser.add_argument("--context-limit", type=int, default=32000)
    parser.add_argument("--output-reserve", type=int, default=4000)
    parser.add_argument("--compact-at", type=int, default=20000)
    add_batch_command(parser.add_subparsers(dest="command"))
    return parser


def run(arguments: argparse.Namespace) -> int:
    return run_cli(
        arguments,
        lambda workspace: create_agent(
            AppConfig(
                cwd=workspace,
                model=arguments.model,
                api_key=arguments.api_key,
                api_base=arguments.api_base,
                provider=arguments.provider,
                session=arguments.session,
                skills=tuple(arguments.skill),
                context_limit=arguments.context_limit,
                output_reserve=arguments.output_reserve,
                compact_at=arguments.compact_at,
            )
        ),
    )


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
