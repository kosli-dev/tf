"""Shared fixtures for tf tests."""

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

# Import bin/tf (no .py extension) as a module named "tf"
_bin_path = str(Path(__file__).resolve().parent.parent / "bin" / "tf")
_loader = importlib.machinery.SourceFileLoader("tf", _bin_path)
_spec = importlib.util.spec_from_loader("tf", _loader)
tf = importlib.util.module_from_spec(_spec)
sys.modules["tf"] = tf
_loader.exec_module(tf)
