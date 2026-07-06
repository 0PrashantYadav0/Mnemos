"""Mnemos: The Town That Never Forgets.

A narrative RPG on a graph-memory NPC Brain. Fully local, no external services.
"""

# Load .env (if present) before anything reads os.environ -- so COGNEE_API_KEY
# and friends are available to the Brain at import time. Best-effort; a missing
# python-dotenv or .env just means we fall back to real shell env vars. We search
# from the current working directory upward (usecwd=True) so it works whether the
# package is installed editable or into site-packages.
#
# Set MNEMOS_SKIP_DOTENV=1 to bypass this entirely (used by the test suite so it
# stays hermetic/offline and never mirrors to Cognee Cloud).
import os as _os

if not _os.environ.get("MNEMOS_SKIP_DOTENV"):
    try:
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv(usecwd=True), override=True)
    except Exception:  # noqa: BLE001
        pass

__version__ = "0.1.0"
