from hatchling.plugin import hookimpl

from .plugin import SbomBuildHook


@hookimpl
def hatch_register_build_hook() -> type[SbomBuildHook]:
    return SbomBuildHook
