"""Read operator-owned user hashes from a mounted file; never print credentials."""

import os
from pathlib import Path

from mmm_intelligence.server import main

if __name__ == "__main__":
    os.environ["MMM_USERS_JSON"] = Path("/run/secrets/mmm_users").read_text(encoding="utf-8")
    main()
