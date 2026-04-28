import subprocess
import sys
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
    hook.initialize("standard", build_data)
    assert "sbom_files" not in build_data


def test_skip_editable_build_without_source(tmp_path: Path) -> None:
    hook = create_hook(tmp_path, {})
    build_data: dict[str, Any] = {}
    hook.initialize("editable", build_data)
    assert "sbom_files" not in build_data


def test_skip_force_include_editable_without_source(tmp_path: Path) -> None:
    hook = create_hook(tmp_path, {})
    build_data: dict[str, Any] = {"force_include_editable": ["package"]}
    hook.initialize("standard", build_data)
    assert "sbom_files" not in build_data


def test_missing_source(tmp_path: Path) -> None:
    hook = create_hook(tmp_path, {})
    build_data: dict[str, Any] = {}
    with pytest.raises(ValueError, match="The 'source' option is required"):
        hook.initialize("standard", build_data)


def test_invalid_source(tmp_path: Path) -> None:
    hook = create_hook(tmp_path, {"source": "invalid_source"})
    build_data: dict[str, Any] = {}
    with pytest.raises(ValueError, match="Unsupported source 'invalid_source'"):
        hook.initialize("standard", build_data)


def test_invalid_format(tmp_path: Path) -> None:
    hook = create_hook(tmp_path, {"source": "environment", "format": "toml"})
    build_data: dict[str, Any] = {}
    with pytest.raises(ValueError, match="Unsupported format 'toml'"):
        hook.initialize("standard", build_data)


def test_uv_rejects_xml_format(tmp_path: Path) -> None:
    hook = create_hook(tmp_path, {"source": "uv", "format": "xml"})
    build_data: dict[str, Any] = {}
    with pytest.raises(ValueError, match="The 'uv' source only supports 'json' format"):
        hook.initialize("standard", build_data)


def test_missing_path_for_requirements(tmp_path: Path) -> None:
    hook = create_hook(tmp_path, {"source": "requirements"})
    build_data: dict[str, Any] = {}
    with pytest.raises(ValueError, match="Could not automatically find a requirements file for source 'requirements'"):
        hook.initialize("standard", build_data)


def test_guess_path_for_requirements(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_run = mocker.patch("subprocess.run")
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("requests")

    hook = create_hook(tmp_path, {"source": "requirements"})
    build_data: dict[str, Any] = {}
    hook.initialize("standard", build_data)

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
    hook.initialize("standard", build_data)

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


def test_finalize_cleans_temp_dir(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch("subprocess.run")
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("requests")

    hook = create_hook(tmp_path, {"source": "requirements"})
    build_data: dict[str, Any] = {}
    hook.initialize("standard", build_data)

    temp_dir = Path(hook._temp_dir.name)
    assert temp_dir.exists()

    hook.finalize("1.0", build_data, "dist/package.whl")

    assert not temp_dir.exists()
    assert not hasattr(hook, "_temp_dir")


def test_finalize_without_temp_dir_is_noop(tmp_path: Path) -> None:
    hook = create_hook(tmp_path, {"source": "requirements"})
    hook.finalize("1.0", {}, "dist/package.whl")
    assert not hasattr(hook, "_temp_dir")


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
    hook.initialize("standard", build_data)

    cmd_args = mock_run.call_args[0][0]
    assert "--pyproject" in cmd_args
    assert pyproject in cmd_args


@pytest.mark.parametrize(
    ("source", "fmt", "expected_filename"),
    [
        ("poetry", "json", "sbom.cdx.json"),
        ("pipenv", "xml", "sbom.cdx.xml"),
        ("environment", "json", "sbom.cdx.json"),
    ],
)
def test_cyclonedx_py_sources(
    mocker: MockerFixture, tmp_path: Path, source: str, fmt: str, expected_filename: str
) -> None:
    mock_run = mocker.patch("subprocess.run")
    output_dir = tmp_path / "dist"
    output_dir.mkdir()

    hook = SbomBuildHook(
        root=str(tmp_path),
        config={
            "source": source,
            "path": ".",
            "format": fmt,
            "spec-version": "1.5",
            source: {
                "validate": True,
                "exclude": ["docs", "test"],
                "mc-type": "application",
                "extra-args": ["--verbose", "--another-option"],
            },
        },
        build_config={},  # type: ignore[arg-type]
        metadata=None,  # type: ignore[arg-type]
        directory=str(output_dir),
        target_name="wheel",
    )

    build_data: dict[str, Any] = {}
    hook.initialize("standard", build_data)

    mock_run.assert_called_once()
    cmd_args = mock_run.call_args[0][0]

    assert cmd_args[0] == "cyclonedx-py"
    assert cmd_args[1] == source
    assert cmd_args[2] == "."
    assert "--output-format" in cmd_args
    assert fmt in cmd_args
    assert "--output-file" in cmd_args
    assert "--spec-version" in cmd_args
    assert "1.5" in cmd_args
    assert "--validate" in cmd_args
    assert cmd_args.count("--exclude") == 2
    assert "docs" in cmd_args
    assert "test" in cmd_args
    assert "--mc-type" in cmd_args
    assert "application" in cmd_args
    assert "--verbose" in cmd_args
    assert "--another-option" in cmd_args

    assert "sbom_files" in build_data
    output_file = Path(build_data["sbom_files"][0])
    assert output_file.name == expected_filename


def test_source_args_ignore_non_dict_config(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_run = mocker.patch("subprocess.run")

    hook = create_hook(tmp_path, {"source": "environment", "environment": ["not", "a", "dict"]})
    build_data: dict[str, Any] = {}
    hook.initialize("standard", build_data)

    cmd_args = mock_run.call_args[0][0]
    assert cmd_args == [
        "cyclonedx-py",
        "environment",
        sys.executable,
        "--output-format",
        "json",
        "--output-file",
        Path(build_data["sbom_files"][0]),
        "--spec-version",
        "1.6",
    ]


def test_source_args_omit_false_bool(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_run = mocker.patch("subprocess.run")

    hook = create_hook(tmp_path, {"source": "environment", "environment": {"validate": False}})
    build_data: dict[str, Any] = {}
    hook.initialize("standard", build_data)

    cmd_args = mock_run.call_args[0][0]
    assert "--validate" not in cmd_args


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

    hook.initialize("standard", build_data)

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


def test_uv_source_allows_disabling_frozen(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_run = mocker.patch("subprocess.run")
    output_dir = tmp_path / "dist"
    output_dir.mkdir()

    hook = SbomBuildHook(
        root=str(tmp_path),
        config={"source": "uv", "format": "json", "uv": {"frozen": False}},
        build_config={},  # type: ignore[arg-type]
        metadata=None,  # type: ignore[arg-type]
        directory=str(output_dir),
        target_name="wheel",
    )

    mock_result = mocker.MagicMock()
    mock_result.stdout = '{"bomFormat": "CycloneDX", "specVersion": "1.5"}'
    mock_run.return_value = mock_result

    build_data: dict[str, Any] = {}
    hook.initialize("standard", build_data)

    cmd_args = mock_run.call_args[0][0]
    assert "--frozen" not in cmd_args


def test_uv_source_failure_includes_process_details(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(2, ["uv", "export"], output="uv stdout", stderr="uv stderr"),
    )

    hook = create_hook(tmp_path, {"source": "uv", "format": "json"})
    build_data: dict[str, Any] = {}

    with pytest.raises(Exception, match="Failed to generate SBOM using uv") as exc_info:
        hook.initialize("standard", build_data)

    message = str(exc_info.value)
    assert "Failed to generate SBOM using uv" in message
    assert "Command: uv export" in message
    assert "Exit code: 2" in message
    assert "Stdout: uv stdout" in message
    assert "Stderr: uv stderr" in message


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

    hook.initialize("standard", build_data)

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


def test_pdm_source_without_path_passes_pyproject_to_cyclonedx(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_run = mocker.patch("subprocess.run")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]")

    mock_pdm_result = mocker.MagicMock()
    mock_pdm_result.stdout = "requests==2.31.0\n"
    mock_run.return_value = mock_pdm_result

    hook = create_hook(tmp_path, {"source": "pdm"})
    build_data: dict[str, Any] = {}
    hook.initialize("standard", build_data)

    pdm_cmd_args = mock_run.call_args_list[0][0][0]
    assert "--project" not in pdm_cmd_args

    cdx_cmd_args = mock_run.call_args_list[1][0][0]
    assert "--pyproject" in cdx_cmd_args
    assert pyproject in cdx_cmd_args


def test_pdm_export_failure_includes_process_details(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(3, ["pdm", "export"], output="pdm stdout", stderr="pdm stderr"),
    )

    hook = create_hook(tmp_path, {"source": "pdm"})
    build_data: dict[str, Any] = {}

    with pytest.raises(Exception, match="Failed to export dependencies using pdm") as exc_info:
        hook.initialize("standard", build_data)

    message = str(exc_info.value)
    assert "Failed to export dependencies using pdm" in message
    assert "Command: pdm export" in message
    assert "Exit code: 3" in message
    assert "Stdout: pdm stdout" in message
    assert "Stderr: pdm stderr" in message


def test_pdm_cyclonedx_failure_includes_process_details(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_pdm_result = mocker.MagicMock()
    mock_pdm_result.stdout = "requests==2.31.0\n"
    mocker.patch(
        "subprocess.run",
        side_effect=[
            mock_pdm_result,
            subprocess.CalledProcessError(
                4, ["cyclonedx-py", "requirements", "-"], output="cdx stdout", stderr="cdx stderr"
            ),
        ],
    )

    hook = create_hook(tmp_path, {"source": "pdm"})
    build_data: dict[str, Any] = {}

    with pytest.raises(Exception, match="Failed to generate SBOM using cyclonedx-py") as exc_info:
        hook.initialize("standard", build_data)

    message = str(exc_info.value)
    assert "Failed to generate SBOM using cyclonedx-py" in message
    assert "Command: cyclonedx-py requirements -" in message
    assert "Exit code: 4" in message
    assert "Stdout: cdx stdout" in message
    assert "Stderr: cdx stderr" in message


def test_cyclonedx_py_failure_includes_process_details(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(
            5, ["cyclonedx-py", "environment"], output="env stdout", stderr="env stderr"
        ),
    )

    hook = create_hook(tmp_path, {"source": "environment"})
    build_data: dict[str, Any] = {}

    with pytest.raises(Exception, match="Failed to generate SBOM using cyclonedx-py") as exc_info:
        hook.initialize("standard", build_data)

    message = str(exc_info.value)
    assert "Failed to generate SBOM using cyclonedx-py" in message
    assert "Command: cyclonedx-py environment" in message
    assert "Exit code: 5" in message
    assert "Stdout: env stdout" in message
    assert "Stderr: env stderr" in message
