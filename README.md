# Hatch SBOM

<table>
  <tbody>
    <tr>
      <th scope="row">CI/CD</th>
      <td>
        <a href="https://github.com/Ichunjo/hatch-sbom/actions/workflows/ci-test.yml"><img src="https://github.com/Ichunjo/hatch-sbom/actions/workflows/ci-test.yml/badge.svg" alt="CI - Test"></a>
        <a href="https://coveralls.io/github/Ichunjo/hatch-sbom?branch=master"><img src="https://coveralls.io/repos/github/Ichunjo/hatch-sbom/badge.svg?branch=master" alt="Coverage Status"></a>
        <a href="https://github.com/Ichunjo/hatch-sbom/actions/workflows/ci-lint.yml"><img src="https://github.com/Ichunjo/hatch-sbom/actions/workflows/ci-lint.yml/badge.svg" alt="CI - Lint"></a>
        <a href="https://github.com/Ichunjo/hatch-sbom/actions/workflows/cd-publish.yml"><img src="https://github.com/Ichunjo/hatch-sbom/actions/workflows/cd-publish.yml/badge.svg" alt="CD - Publish"></a>
      </td>
    </tr>
    <tr>
      <th scope="row">Package</th>
      <td>
        <a href="https://pypi.org/project/hatch-sbom/"><img src="https://img.shields.io/pypi/v/hatch-sbom.svg?logo=pypi&label=PyPI&logoColor=gold" alt="PyPI - Version"></a>
        <a href="https://pypi.org/project/hatch-sbom/"><img src="https://img.shields.io/pypi/pyversions/hatch-sbom.svg?logo=python&label=Python&logoColor=gold" alt="PyPI - Python Version"></a>
      </td>
    </tr>
    <tr>
      <th scope="row">Meta</th>
      <td>
        <a href="https://github.com/pypa/hatch"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pypa/hatch/master/docs/assets/badge/v0.json" alt="Hatch project"></a>
        <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="linting - Ruff"></a>
        <a href="https://github.com/python/mypy"><img src="https://img.shields.io/badge/types-Mypy-blue.svg" alt="types - Mypy"></a>
        <a href="https://spdx.org/licenses/MIT.html"><img src="https://img.shields.io/badge/license-MIT-9400d3.svg" alt="License - MIT"></a>
      </td>
    </tr>
  </tbody>
</table>

---

A Hatchling build hook plugin to automatically generate a Software Bill of Materials (SBOM) during wheel creation.

## Usage

To use this plugin, configure your `pyproject.toml` to require both `hatchling` (>=1.28.0) and `hatch-sbom` in your `build-system`.

For a `requirements.txt` SBOM:

```toml
[build-system]
requires = ["hatchling>=1.28.0", "hatch-sbom[cdx]"]
build-backend = "hatchling.build"
```

The base install is minimal. Install extras only for the backend used by your selected source:

- `requirements`, `poetry`, `pipenv`, and `environment` use `cyclonedx-py` and need `hatch-sbom[cdx]`.
- `uv` uses `uv export` directly and needs `hatch-sbom[uv]`.
- `pdm` uses both `pdm export` and `cyclonedx-py`, so it needs `hatch-sbom[pdm,cdx]`.

Next, configure the build hook specifically for the `wheel` target:

```toml
[tool.hatch.build.targets.wheel.hooks.sbom]
source = "requirements"
path = "requirements.txt"
format = "json"        # Optional, defaults to "json"
spec-version = "1.6"   # Optional, defaults to "1.6"
```

### Supported Sources

The `source` field determines how the SBOM is built.

| Source         | Requires              | Backend                                        | Path behavior                                                     |
| -------------- | --------------------- | ---------------------------------------------- | ----------------------------------------------------------------- |
| `requirements` | `hatch-sbom[cdx]`     | `cyclonedx-py requirements`                    | Optional; defaults to `requirements.txt` when present.            |
| `poetry`       | `hatch-sbom[cdx]`     | `cyclonedx-py poetry`                          | Optional; defaults to the current directory.                      |
| `pipenv`       | `hatch-sbom[cdx]`     | `cyclonedx-py pipenv`                          | Optional; defaults to the current directory.                      |
| `environment`  | `hatch-sbom[cdx]`     | `cyclonedx-py environment`                     | Optional; defaults to the current directory.                      |
| `uv`           | `hatch-sbom[uv]`      | `uv export`                                    | Optional; defaults to the current directory. Requires `uv.lock`.  |
| `pdm`          | `hatch-sbom[pdm,cdx]` | `pdm export`, then `cyclonedx-py requirements` | Optional; defaults to the current directory. Requires `pdm.lock`. |

The `uv` source only supports `json` format and CycloneDX `1.5`.

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
