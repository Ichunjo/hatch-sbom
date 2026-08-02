import sys
from pathlib import Path
from typing import Any

# Add the src directory to the module search path so we can import the local plugin
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from hatch_sbom.plugin import SbomBuildHook  # noqa: E402


class CustomSbomBuildHook(SbomBuildHook):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        del self.config["path"]
        return super().initialize(version, build_data)


def get_build_hook() -> type[CustomSbomBuildHook]:
    return CustomSbomBuildHook
