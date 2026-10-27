"""No installers or shell commands: use the operator-selected Python environment."""

import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
bundled = root / "server"
if bundled.is_dir():
    sys.path.insert(0, str(bundled))
# Explicitly local stdio. Data remains outside the immutable plugin package.
os.environ["MMM_TRANSPORT"] = "stdio"
os.environ.setdefault("MMM_DATA_DIR", str(Path.home() / ".mmm-intelligence" / "plugin-data"))
from mmm_intelligence.server import main  # noqa: E402

if __name__ == "__main__":
    main()
