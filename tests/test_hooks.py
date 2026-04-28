from hatch_sbom.hooks import hatch_register_build_hook
from hatch_sbom.plugin import SbomBuildHook


def test_hatch_register_build_hook() -> None:
    assert hatch_register_build_hook() is SbomBuildHook
