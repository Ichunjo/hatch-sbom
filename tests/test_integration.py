import json
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import build
import pytest


def run_integration_test(
    tmp_path: Path,
    source: str,
    config: dict[str, Any] | None = None,
    setup_files: dict[str, str] | None = None,
    build_from_sdist: bool = False,
    extra_requires: str = "",
) -> None:
    project_dir = tmp_path / f"test_project_{source}_{'sdist' if build_from_sdist else 'direct'}"
    project_dir.mkdir()

    current_dir_uri = Path.cwd().as_uri()

    # Base config
    sbom_config: dict[str, Any] = {"source": source}
    if config:
        sbom_config.update(config)

    # Convert config to TOML-like string for the hook
    config_lines = [f'{k} = "{v}"' if isinstance(v, str) else f"{k} = {json.dumps(v)}" for k, v in sbom_config.items()]
    config_toml = "\n".join(config_lines)

    pyproject = project_dir / "pyproject.toml"
    pyproject.write_text(f"""
[build-system]
requires = ["hatchling>=1.28.0", "hatch-sbom[cdx] @ {current_dir_uri}"{extra_requires}]
build-backend = "hatchling.build"

[project]
name = "test-project"
version = "0.0.1"
requires-python = ">=3.12"

[tool.hatch.build.targets.wheel.hooks.sbom]
{config_toml}
""")

    if setup_files:
        for name, content in setup_files.items():
            (project_dir / name).write_text(content)

    package_dir = project_dir / "test_project"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("")

    dist_dir = project_dir / "dist"

    builder = build.ProjectBuilder(project_dir)

    if build_from_sdist:
        # Build sdist
        sdist_path = builder.build("sdist", dist_dir)

        # Unpack sdist
        sdist_extract_dir = tmp_path / f"extract_{source}"
        with tarfile.open(sdist_path) as tf:
            tf.extractall(sdist_extract_dir)

        # Build wheel from unpacked sdist
        sdist_root = next(sdist_extract_dir.iterdir())
        build.ProjectBuilder(sdist_root).build("wheel", dist_dir)
    else:
        # Build wheel directly
        builder.build("wheel", dist_dir)

    wheels = list(dist_dir.glob("*.whl"))
    assert len(wheels) >= 1

    # Check the latest wheel
    wheel_path = sorted(wheels, key=lambda p: p.stat().st_mtime)[-1]
    with zipfile.ZipFile(wheel_path) as z:
        namelist = z.namelist()
        sbom_files = [n for n in namelist if n.endswith("sbom.cdx.json")]
        assert len(sbom_files) == 1

        with z.open(sbom_files[0]) as f:
            data = json.load(f)
            assert "bomFormat" in data
            assert data["bomFormat"] == "CycloneDX"


@pytest.mark.parametrize(
    ("source", "config", "setup_files", "extra_requires"),
    [
        ("requirements", {"path": "requirements.txt"}, {"requirements.txt": "requests==2.31.0\n"}, ""),
        ("environment", {}, {}, ""),
    ],
)
def test_integration_sources_direct(
    tmp_path: Path, source: str, config: dict[str, Any], setup_files: dict[str, str], extra_requires: str
) -> None:
    run_integration_test(tmp_path, source, config, setup_files, build_from_sdist=False, extra_requires=extra_requires)


def test_integration_sdist_to_wheel(tmp_path: Path) -> None:
    # Use requirements as a representative case for sdist-to-wheel
    run_integration_test(
        tmp_path,
        "requirements",
        {"path": "requirements.txt"},
        {"requirements.txt": "requests==2.31.0\n"},
        build_from_sdist=True,
        extra_requires="",
    )
