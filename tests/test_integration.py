import json
import pathlib
import zipfile

import build


def test_integration(tmp_path: pathlib.Path) -> None:
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    current_dir_uri = pathlib.Path.cwd().as_uri()

    pyproject = project_dir / "pyproject.toml"
    pyproject.write_text(f"""
[build-system]
requires = ["hatchling>=1.28.0", "hatch-sbom @ {current_dir_uri}"]
build-backend = "hatchling.build"

[project]
name = "test-project"
version = "0.0.1"
requires-python = ">=3.12"

[tool.hatch.build.targets.wheel.hooks.sbom]
source = "requirements"
path = "requirements.txt"
""")

    req_file = project_dir / "requirements.txt"
    req_file.write_text("requests==2.31.0\n")

    package_dir = project_dir / "test_project"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("")

    dist_dir = project_dir / "dist"
    build.ProjectBuilder(project_dir).build("wheel", dist_dir)

    wheels = list(dist_dir.glob("*.whl"))
    assert len(wheels) == 1

    wheel_path = wheels[0]
    with zipfile.ZipFile(wheel_path) as z:
        namelist = z.namelist()
        sbom_files = [n for n in namelist if n.endswith("sbom.cdx.json")]
        assert len(sbom_files) == 1

        # Optionally, read it to verify it's valid JSON
        with z.open(sbom_files[0]) as f:
            data = json.load(f)
            assert "bomFormat" in data
            assert data["bomFormat"] == "CycloneDX"
