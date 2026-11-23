"""Load the node package from its folder, hyphenated name and all.

ComfyUI imports a custom-node folder as a package, so the tests do the same:
one spec with `submodule_search_locations`, then import the submodules normally.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "arkflex"


def load_package():
    if NAME in sys.modules:
        return sys.modules[NAME]
    spec = importlib.util.spec_from_file_location(
        NAME,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("could not build a package spec for the node folder")
    module = importlib.util.module_from_spec(spec)
    sys.modules[NAME] = module
    spec.loader.exec_module(module)
    return module


load_package()
