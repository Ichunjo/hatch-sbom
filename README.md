# hatch-sbom

[![PyPI - Version](https://img.shields.io/pypi/v/hatch-sbom.svg)](https://pypi.org/project/hatch-sbom)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/hatch-sbom.svg)](https://pypi.org/project/hatch-sbom)
[![Tests](https://github.com/Ichunjo/hatch-sbom/actions/workflows/ci-test.yml/badge.svg)](https://github.com/Ichunjo/hatch-sbom/actions/workflows/ci-test.yml)
[![Lint](https://github.com/Ichunjo/hatch-sbom/actions/workflows/ci-lint.yml/badge.svg)](https://github.com/Ichunjo/hatch-sbom/actions/workflows/ci-lint.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Hatchling build hook plugin to automatically generate a Software Bill of Materials (SBOM) during wheel creation using `cyclonedx-py`.

## Usage

To use this plugin, you must configure your `pyproject.toml` to require both `hatchling` (>=1.28.0) and `hatch-sbom` in your `build-system`:

```toml
[build-system]
requires = ["hatchling>=1.28.0", "hatch-sbom"]
build-backend = "hatchling.build"
```

Next, configure the build hook specifically for the `wheel` target:

```toml
[tool.hatch.build.targets.wheel.hooks.sbom]
source = "requirements"
path = "requirements.txt"
format = "json"        # Optional, defaults to "json"
spec-version = "1.6"   # Optional, defaults to "1.6"
```

### Supported Sources

The `source` field determines how the SBOM is built, mapping to the respective `cyclonedx-py` commands:

- `requirements`: Build an SBOM from Pip requirements.
  The `path` option is optional; if omitted, the plugin will automatically look for `requirements.txt`.
- `poetry`: Build an SBOM from a Poetry project.
  The `path` option is optional and defaults to the current directory.
- `pipenv`: Build an SBOM from a Pipenv manifest.
  The `path` option is optional and defaults to the current directory.
- `environment`: Build an SBOM from a Python environment.
  The `path` option is optional and defaults to the current directory.
- `uv`: Build an SBOM using `uv export`. Requires a `uv.lock` file.
  The `path` option is optional and defaults to the current directory.
  Only supports `json` format and `1.5` spec-version.
- `pdm`: Build an SBOM using `pdm export` and `cyclonedx-py`. Requires a `pdm.lock` file.
  The `path` option is optional and defaults to the current directory.

### Source-Specific Arguments

You can pass extra arguments to the underlying tool (e.g., `uv export`, `pdm export`, or `cyclonedx-py <source>`) by creating a nested table named after the source.

This is useful for passing flags like `--without`, `--no-dev`, etc.

For example, to omit the `dev` and `test` groups when using Poetry:

```toml
[tool.hatch.build.targets.wheel.hooks.sbom.poetry]
without = ["dev", "test"]  # Appends `--without dev --without test`
```

To include all extras when using uv:

```toml
[tool.hatch.build.targets.wheel.hooks.sbom.uv]
all-extras = true  # Appends `--all-extras`
```

You can use the `extra-args` key to pass an arbitrary list of raw arguments:

```toml
[tool.hatch.build.targets.wheel.hooks.sbom.pipenv]
extra-args = ["--mc-type", "firmware"]
```

The generated SBOM file (e.g., `sbom.cdx.json`) will be automatically placed in the `.dist-info/sboms/` directory of the resulting wheel.
