from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

EXCLUDED_PARTS = {".venv", ".pytest_cache", "__pycache__", "dist", ".git"}


def package_companion(source: Path, output: Path) -> int:
    if not source.is_dir():
        raise FileNotFoundError(f"Companion project folder not found: {source}")

    output.parent.mkdir(parents=True, exist_ok=True)
    included = 0
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in source.rglob("*"):
            if not path.is_file() or any(part in EXCLUDED_PARTS for part in path.parts):
                continue
            archive.write(path, path.as_posix())
            included += 1

    if included == 0 or output.stat().st_size == 0:
        output.unlink(missing_ok=True)
        raise RuntimeError("Companion project archive would be empty")
    return included


def main() -> None:
    parser = argparse.ArgumentParser(description="Package the companion metrics service")
    parser.add_argument("--source", type=Path, default=Path("companion-metrics-server"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("release-assets/DashboardLMStudio_MetricsServer.zip"),
    )
    args = parser.parse_args()
    count = package_companion(args.source, args.output)
    print(f"Packaged {count} files into {args.output}")


if __name__ == "__main__":
    main()
