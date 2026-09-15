"""Thin wrapper: the probe now lives in projectionlab_mcp.probe (also `projectionlab probe ...`)."""
import os, sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault("PROJECTIONLAB_ROOT", PROJECT_ROOT)
from projectionlab_mcp.probe import main  # noqa: E402

if __name__ == "__main__":
    main()
