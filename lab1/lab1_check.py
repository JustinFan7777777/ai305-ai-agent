"""练习一检查脚本：只读检查目录及保存命令输出的文件。"""

import argparse
from pathlib import Path


def check_directory(root: Path) -> list[tuple[str, bool, str]]:
    """检查所需目录和文件内容，不修改任何文件。"""
    checks = []
    for name in ("project", "results"):
        checks.append((name, (root / name).is_dir(), "required directory"))

    expected = {
        "project/project.txt": [
            "project=demo-agent", "language=python", "interface=terminal",
        ],
        "results/preview.txt": ["# Demo Agent Workspace", "", "Project: demo-agent"],
        "results/errors.txt": ["ERROR input file missing"],
    }
    for name in expected:
        path = root / name
        try:
            if path.is_symlink() or not path.is_file():
                raise ValueError("expected a regular file, not a link")
            text = path.read_text(encoding="utf-8")
            ok = text.splitlines() == expected[name]
            detail = "content must match the required command output"
            checks.append((name, ok, detail))
        except (OSError, UnicodeError, ValueError) as error:
            checks.append((name, False, str(error)))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root", nargs="?", type=Path,
        default=Path(__file__).resolve().parent / "submission",
    )
    args = parser.parse_args()
    checks = check_directory(args.root)
    for name, ok, detail in checks:
        print(f"{'PASS' if ok else 'FAIL'} {name}" + ("" if ok else f": {detail}"))
    passed = all(ok for _, ok, _ in checks)
    print("PASS: Exercise 1 complete." if passed else "FAIL: Fix the items above and retry.")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
