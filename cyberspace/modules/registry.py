"""Module discovery: finds and loads all cyberspace modules.

Built-in modules live under modules_ib / modules_ab / modules_sd / modules_cd
packages. External modules are any installed package named `cyberspace_module_*`
exposing a `MODULE` Module subclass attribute.
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import Optional

from .base import LOADED_MODULES, Module, TOOL_REGISTRY


def _load_one(module_path: str, attr: str = "MODULE") -> Optional[Module]:
    try:
        mod = importlib.import_module(module_path)
    except Exception:
        return None
    obj = getattr(mod, attr, None)
    if isinstance(obj, Module):
        return obj
    return None


def discover_and_load() -> dict[str, Module]:
    """Discover built-in modules and register their tools + CLIs.

    Returns the LOADED_MODULES map {name: Module}.
    """
    builtins = [
        "cyberspace.platforms.iceberg.module",
        "cyberspace.platforms.airbender.module",
        "cyberspace.platforms.shadowdragon.module",
        "cyberspace.platforms.stickem.module",
        "cyberspace.platforms.trainababy.module",
    ]
    for path in builtins:
        m = _load_one(path)
        if m:
            info = m.describe()
            LOADED_MODULES[info.name] = m
            m.register_tools(TOOL_REGISTRY)

    # External modules: scan for installed cyberspace_module_* packages.
    try:
        for finder, name, ispkg in pkgutil.iter_modules():
            if name.startswith("cyberspace_module_"):
                m = _load_one(name, "MODULE")
                if m:
                    info = m.describe()
                    LOADED_MODULES[info.name] = m
                    m.register_tools(TOOL_REGISTRY)
    except Exception:
        pass

    return LOADED_MODULES
