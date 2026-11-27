from __future__ import annotations

import importlib.util
from pathlib import Path
from zipfile import ZipFile

PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parent
PACKAGER = REPO / ".github" / "scripts" / "package_companion.py"


def _load_packager():
    spec = importlib.util.spec_from_file_location("package_companion", PACKAGER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_zip_is_flat_and_runnable(tmp_path: Path) -> None:
    """The extracted folder must itself be the uv project (issue #2)."""
    output = tmp_path / "companion.zip"
    package_companion = _load_packager()
    assert package_companion.package_companion(PROJECT, output) > 0

    with ZipFile(output) as archive:
        names = set(archive.namelist())

    assert "pyproject.toml" in names
    assert "uv.lock" in names
    assert "src/metrics_server/app.py" in names
    assert "src/metrics_server/web/index.html" in names
    assert "start.bat" in names
    assert "start.sh" in names

    # A nested companion-metrics-server/ folder is what made the documented
    # `uv run uvicorn metrics_server.app:app` command fail with ModuleNotFoundError.
    assert not any(name.startswith("companion-metrics-server/") for name in names)
