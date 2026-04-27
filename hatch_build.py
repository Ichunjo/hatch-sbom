import sys
from pathlib import Path

# Add the src directory to the module search path so we can import the local plugin
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from hatch_sbom.plugin import SbomBuildHook  # noqa: E402


def get_build_hook() -> type[SbomBuildHook]:
    return SbomBuildHook
