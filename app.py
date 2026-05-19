"""FastAPI app entry point (Render / production).

Delegates to the canonical web module so behaviour stays in sync.
"""

import sys
from pathlib import Path

# Ensure the src layout is importable
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vallejo_scraper.web import app  # noqa: F401, E402
