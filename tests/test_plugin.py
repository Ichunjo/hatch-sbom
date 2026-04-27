from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture

from hatch_sbom.plugin import SbomBuildHook


def create_hook(tmp_path: Path, config: dict[str, Any], target_name: str = "wheel") -> SbomBuildHook:
    return SbomBuildHook(
        root=str(tmp_path),
        config=config,
        build_config={},  # type: ignore[arg-type]
        metadata=None,  # type: ignore[arg-type]
        directory=str(tmp_path),
        target_name=target_name,
    )


def test_skip_non_wheel(tmp_path: Path) -> None:
    hook = create_hook(tmp_path, {"source": "requirements"}, target_name="sdist")
    build_data: dict[str, Any] = {}
    hook.initialize("1.0", build_data)
    assert "sbom_files" not in build_data


def test_missing_source(tmp_path: Path) -> None:
    hook = create_hook(tmp_path, {})
    build_data: dict[str, Any] = {}
    with pytest.raises(ValueError, match="The 'source' option is required"):
        hook.initialize("1.0", build_data)


def test_invalid_source(tmp_path: Path) -> None:
    hook = create_hook(tmp_path, {"source": "invalid_source"})
    build_data: dict[str, Any] = {}
    with pytest.raises(ValueError, match="Unsupported source 'invalid_source'"):
        hook.initialize("1.0", build_data)


def test_missing_path_for_requirements(tmp_path: Path) -> None:
    hook = create_hook(tmp_path, {"source": "requirements"})
    build_data: dict[str, Any] = {}
    with pytest.raises(ValueError, match="Could not automatically find a requirements file for source 'requirements'"):
        hook.initialize("1.0", build_data)


def test_guess_path_for_requirements(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_run = mocker.patch("subprocess.run")
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("requests")

    hook = create_hook(tmp_path, {"source": "requirements"})
    build_data: dict[str, Any] = {}
    hook.initialize("1.0", build_data)

    mock_run.assert_called_once()
    cmd_args = mock_run.call_args[0][0]
    assert cmd_args[0] == "cyclonedx-py"
    assert cmd_args[1] == "requirements"
    assert cmd_args[2] == "requirements.txt"


def test_valid_requirements_config(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_run = mocker.patch("subprocess.run")
    output_dir = tmp_path / "dist"
    output_dir.mkdir()

    hook = SbomBuildHook(
        root=str(tmp_path),
        config={
            "source": "requirements",
            "path": "requirements.txt",
            "format": "json",
            "requirements": {
                "no-dev": True,
                "without": ["docs", "test"],
                "mc-type": "application",
                "extra-args": ["-v", "-v"],
            },
        },
        build_config={},  # type: ignore[arg-type]
        metadata=None,  # type: ignore[arg-type]
        directory=str(output_dir),
        target_name="wheel",
    )

    build_data: dict[str, Any] = {}
    hook.initialize("1.0", build_data)

    mock_run.assert_called_once()

    cmd_args = mock_run.call_args[0][0]
    assert cmd_args[0] == "cyclonedx-py"
    assert cmd_args[1] == "requirements"
    assert cmd_args[2] == "requirements.txt"
    assert "--output-format" in cmd_args
    assert "json" in cmd_args
    assert "--no-dev" in cmd_args
    assert "--without" in cmd_args
    assert "docs" in cmd_args
    assert "test" in cmd_args
    assert "--mc-type" in cmd_args
    assert "application" in cmd_args
    assert cmd_args.count("-v") == 2

    assert "sbom_files" in build_data
    assert len(build_data["sbom_files"]) == 1
    assert build_data["sbom_files"][0].endswith("sbom.cdx.json")


def test_pyproject_passed_if_exists(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_run = mocker.patch("subprocess.run")
    output_dir = tmp_path / "dist"
    output_dir.mkdir()

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]")

    hook = SbomBuildHook(
        root=str(tmp_path),
        config={
            "source": "environment",
        },
        build_config={},  # type: ignore[arg-type]
        metadata=None,  # type: ignore[arg-type]
        directory=str(output_dir),
        target_name="wheel",
    )

    build_data: dict[str, Any] = {}
    hook.initialize("1.0", build_data)

    cmd_args = mock_run.call_args[0][0]
    assert "--pyproject" in cmd_args
    assert pyproject in cmd_args


def test_uv_source(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_run = mocker.patch("subprocess.run")
    output_dir = tmp_path / "dist"
    output_dir.mkdir()

    hook = SbomBuildHook(
        root=str(tmp_path),
        config={"source": "uv", "path": ".", "format": "json", "uv": {"all-extras": True, "no-group": ["dev"]}},
        build_config={},  # type: ignore[arg-type]
        metadata=None,  # type: ignore[arg-type]
        directory=str(output_dir),
        target_name="wheel",
    )

    build_data: dict[str, Any] = {}

    # Mock the subprocess.run result
    mock_result = mocker.MagicMock()
    mock_result.stdout = '{"bomFormat": "CycloneDX", "specVersion": "1.5"}'
    mock_run.return_value = mock_result

    hook.initialize("1.0", build_data)

    mock_run.assert_called_once()
    cmd_args = mock_run.call_args[0][0]

    assert cmd_args[0] == "uv"
    assert cmd_args[1] == "export"
    assert cmd_args[2] == "--format"
    assert cmd_args[3] == "cyclonedx1.5"
    assert "--project" in cmd_args
    assert "." in cmd_args
    assert "--all-extras" in cmd_args
    assert "--no-group" in cmd_args
    assert "dev" in cmd_args

    assert "sbom_files" in build_data
    output_file = Path(build_data["sbom_files"][0])
    assert output_file.name == "sbom.cdx.json"
    assert output_file.read_text(encoding="utf-8") == mock_result.stdout


def test_pdm_source(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_run = mocker.patch("subprocess.run")
    output_dir = tmp_path / "dist"
    output_dir.mkdir()

    hook = SbomBuildHook(
        root=str(tmp_path),
        config={"source": "pdm", "path": ".", "format": "json", "pdm": {"prod": True, "without": ["test"]}},
        build_config={},  # type: ignore[arg-type]
        metadata=None,  # type: ignore[arg-type]
        directory=str(output_dir),
        target_name="wheel",
    )

    build_data: dict[str, Any] = {}

    # Mock the subprocess.run results (first for pdm export, second for cyclonedx-py)
    mock_pdm_result = mocker.MagicMock()
    mock_pdm_result.stdout = "requests==2.31.0\n"

    mock_cdx_result = mocker.MagicMock()
    mock_cdx_result.stdout = ""

    # Return mock_pdm_result for the first call, mock_cdx_result for the second
    mock_run.side_effect = [mock_pdm_result, mock_cdx_result]

    hook.initialize("1.0", build_data)

    assert mock_run.call_count == 2

    # Check pdm export call
    pdm_cmd_args = mock_run.call_args_list[0][0][0]
    assert pdm_cmd_args[0] == "pdm"
    assert pdm_cmd_args[1] == "export"
    assert pdm_cmd_args[2] == "-f"
    assert pdm_cmd_args[3] == "requirements"
    assert "--without-hashes" in pdm_cmd_args
    assert "--project" in pdm_cmd_args
    assert "." in pdm_cmd_args
    assert "--prod" in pdm_cmd_args
    assert "--without" in pdm_cmd_args
    assert "test" in pdm_cmd_args

    # Check cyclonedx-py call
    cdx_cmd_args = mock_run.call_args_list[1][0][0]
    assert cdx_cmd_args[0] == "cyclonedx-py"
    assert cdx_cmd_args[1] == "requirements"
    assert cdx_cmd_args[2] == "-"
    assert "--output-format" in cdx_cmd_args

    # Check input argument for cyclonedx-py call
    assert mock_run.call_args_list[1][1].get("input") == mock_pdm_result.stdout

    assert "sbom_files" in build_data
    output_file = Path(build_data["sbom_files"][0])
    assert output_file.name == "sbom.cdx.json"
