# -*- coding: utf-8 -*-
"""Shim package to allow importing the `astros-intelligence` code as `astros_intelligence`.
The actual source lives in the sibling directory `astros-intelligence` (contains a hyphen).
This shim extends this package's __path__ to include that directory, making submodule imports work.
"""

import sys
from pathlib import Path
import importlib

# Workspace root (AstroOS)
ROOT = Path(__file__).resolve().parent  # AstroOS root directory
SOURCE_DIR = ROOT.parent / "astros-intelligence"

# Add source directory to sys.path
# Source directory is added via __path__ below; no need to modify sys.path.

# Extend this package's __path__
if hasattr(sys.modules[__name__], "__path__"):
    sys.modules[__name__].__path__.append(str(SOURCE_DIR))
else:
    __path__ = [str(SOURCE_DIR)]

# Pre‑load known subpackages so that `import astros_intelligence.astronomy` works
for subpkg in ("astronomy", "backend_interface", "ranking_engine", "recommendation_engine",
               "observation_optimizer", "explanation_engine"):
    try:
        # Import with full package name so it registers under astros_intelligence.
        full_name = f"{__name__}.{subpkg}"
        module = importlib.import_module(full_name)
        sys.modules[full_name] = module
        # Also expose as top-level name for absolute imports used in the intelligence code.
        sys.modules[subpkg] = module
    except Exception:
        # Fallback: try importing the submodule as a top‑level name (for safety).
        try:
            module = importlib.import_module(subpkg)
            sys.modules[f"{__name__}.{subpkg}"] = module
        except Exception:
            pass
