import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from hatchling.builders.wheel import WheelBuilderConfig


class SbomBuildHook(BuildHookInterface[WheelBuilderConfig]):
    PLUGIN_NAME = "sbom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        is_editable = version == "editable" or len(build_data.setdefault("force_include_editable", [])) > 0

        if self.target_name != "wheel":
            self.app.display_debug("Skipping SBOM generation: target_name != wheel")
            return

        if is_editable:
            self.app.display_debug("Skipping SBOM generation: editable build")
            return

        source = self.config.get("source")
        if not source:
            raise ValueError("The 'source' option is required for the 'sbom' build hook")

        valid_sources = {"requirements", "poetry", "pipenv", "environment", "uv", "pdm"}
        if source not in valid_sources:
            raise ValueError(f"Unsupported source '{source}'. Valid sources are: {', '.join(valid_sources)}")

        path = self.config.get("path")
        if not path and source == "requirements":
            if (Path(self.root) / "requirements.txt").exists():
                path = "requirements.txt"
            else:
                raise ValueError(
                    f"Could not automatically find a requirements file for source '{source}'. "
                    "Please specify the 'path' option."
                )
            # Other sources (poetry, pipenv, uv, pdm, environment) default to the current directory
            # so they do not strictly require a 'path'.

        fmt = self.config.get("format", "json")
        if fmt not in ("json", "xml"):
            raise ValueError(f"Unsupported format '{fmt}'. Valid formats are 'json' or 'xml'")

        if source == "uv" and fmt != "json":
            raise ValueError("The 'uv' source only supports 'json' format")

        spec_version = self.config.get("spec-version", "1.6")

        output_ext = "json" if fmt == "json" else "xml"
        output_filename = f"sbom.cdx.{output_ext}"

        # Use a temporary directory to avoid leaking the SBOM file into the build directory
        self._temp_dir = tempfile.TemporaryDirectory()
        output_path = Path(self._temp_dir.name) / output_filename

        match source:
            case "uv":
                self._generate_uv_sbom(path, output_path)
            case "pdm":
                self._generate_pdm_sbom(path, output_path, fmt, spec_version)
            case _:
                self._generate_sbom(source, path, output_path, fmt, spec_version)

        build_data.setdefault("sbom_files", []).append(str(output_path))

    def finalize(self, version: str, build_data: dict[str, Any], artifact_path: str) -> None:
        if hasattr(self, "_temp_dir"):
            self._temp_dir.cleanup()
            del self._temp_dir

    def _generate_uv_sbom(self, path: str | Path | None, output_path: Path) -> None:
        cmd: list[str | Path] = ["uv", "export", "--format", "cyclonedx1.5"]

        # Default to frozen=True unless explicitly set to False by the user
        if self.config.get("uv", {}).get("frozen", True):
            cmd.append("--frozen")

        if path:
            cmd.extend(["--project", path])

        self._append_source_args(cmd, "uv", skip={"frozen"})

        # Clear UV_PROJECT_ENVIRONMENT to avoid interacting with the parent uv process's environment
        env = os.environ.copy()
        env.pop("UV_PROJECT_ENVIRONMENT", None)

        try:
            result = subprocess.run(cmd, cwd=self.root, check=True, capture_output=True, text=True, env=env)
            output_path.write_text(result.stdout)
        except subprocess.CalledProcessError as e:
            raise Exception(
                f"Failed to generate SBOM using uv:\n"
                f"Command: {' '.join(e.cmd)}\n"
                f"Exit code: {e.returncode}\n"
                f"Stdout: {e.stdout}\n"
                f"Stderr: {e.stderr}"
            ) from e

    def _generate_pdm_sbom(self, path: str | Path | None, output_path: Path, fmt: str, spec_version: str) -> None:
        pdm_cmd: list[str | Path] = ["pdm", "export", "-f", "requirements", "--without-hashes"]
        if path:
            pdm_cmd.extend(["--project", path])

        self._append_source_args(pdm_cmd, "pdm")

        try:
            export_result = subprocess.run(pdm_cmd, cwd=self.root, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise Exception(
                f"Failed to export dependencies using pdm:\n"
                f"Command: {' '.join(e.cmd)}\n"
                f"Exit code: {e.returncode}\n"
                f"Stdout: {e.stdout}\n"
                f"Stderr: {e.stderr}"
            ) from e

        cmd: list[str | Path] = ["cyclonedx-py", "requirements", "-"]
        cmd.extend(["--output-format", fmt, "--output-file", output_path, "--spec-version", spec_version])

        pyproject_path = Path(self.root) / "pyproject.toml"
        if pyproject_path.exists():
            cmd.extend(["--pyproject", pyproject_path])

        try:
            subprocess.run(cmd, cwd=self.root, check=True, capture_output=True, text=True, input=export_result.stdout)
        except subprocess.CalledProcessError as e:
            raise Exception(
                f"Failed to generate SBOM using cyclonedx-py:\n"
                f"Command: {' '.join(e.cmd)}\n"
                f"Exit code: {e.returncode}\n"
                f"Stdout: {e.stdout}\n"
                f"Stderr: {e.stderr}"
            ) from e

    def _generate_sbom(
        self, source: str, path: str | Path | None, output_path: Path, fmt: str, spec_version: str
    ) -> None:
        cmd: list[str | Path] = ["cyclonedx-py", source]
        if path:
            cmd.append(path)
        cmd.extend(["--output-format", fmt, "--output-file", output_path, "--spec-version", spec_version])

        pyproject_path = Path(self.root) / "pyproject.toml"
        if pyproject_path.exists():
            cmd.extend(["--pyproject", pyproject_path])

        self._append_source_args(cmd, source)

        try:
            subprocess.run(cmd, cwd=self.root, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise Exception(
                f"Failed to generate SBOM using cyclonedx-py:\n"
                f"Command: {' '.join(e.cmd)}\n"
                f"Exit code: {e.returncode}\n"
                f"Stdout: {e.stdout}\n"
                f"Stderr: {e.stderr}"
            ) from e

    def _append_source_args(self, cmd: list[str | Path], source: str, skip: set[str] | None = None) -> None:
        source_config = self.config.get(source, {})
        if not isinstance(source_config, dict):
            return

        skip = skip or set()
        for key, value in source_config.items():
            if key in skip:
                continue

            if key == "extra-args" and isinstance(value, list):
                cmd.extend(str(v) for v in value)
            elif isinstance(value, bool):
                if value:
                    cmd.append(f"--{key}")
            elif isinstance(value, list):
                for item in value:
                    cmd.extend([f"--{key}", str(item)])
            else:
                cmd.extend([f"--{key}", str(value)])
