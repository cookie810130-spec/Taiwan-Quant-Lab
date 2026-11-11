"""Hidden scheduled-task runner; redirect errors to user's local log."""
from pathlib import Path
import os
import sys

base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "TaiwanQuantLab"
base.mkdir(parents=True, exist_ok=True)
with (base / "server.log").open("a", encoding="utf-8", buffering=1) as log:
    sys.stdout = log
    sys.stderr = log
    from quantlab.v2.server import main
    main()
