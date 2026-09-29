"""Makes `import fusionscript` work on Windows.

Fusion ships its scripting module as fusionscript.dll, which a plain import
does not pick up (Python only imports .pyd). fusion-studio-mcp does
`importlib.import_module("fusionscript")`, so this stand-in loads the DLL
from FUSION_DLL and replaces itself with it.
"""

import importlib.machinery
import importlib.util
import os
import sys

_dll = os.environ.get("FUSION_DLL", "")
if not os.path.isfile(_dll):
    raise ImportError(f"fusionscript.dll not found (FUSION_DLL={_dll!r}); re-run install.ps1 -FusionDll <path>")

_loader = importlib.machinery.ExtensionFileLoader("fusionscript", _dll)
_spec = importlib.util.spec_from_file_location("fusionscript", _dll, loader=_loader)
_module = importlib.util.module_from_spec(_spec)
_loader.exec_module(_module)
sys.modules[__name__] = _module
