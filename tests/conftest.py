"""Test configuration for Mnemos.

Keeps the suite hermetic: it runs fully offline against the local typed graph
and never touches Cognee Cloud, regardless of a .env file or an exported
COGNEE_API_KEY on the machine (or in CI). This must run *before* the ``mnemos``
package is imported, so it lives at import time in conftest.
"""
import os

# Bypass the .env auto-load in mnemos/__init__.py and force local-only mode.
os.environ["MNEMOS_SKIP_DOTENV"] = "1"
os.environ.pop("COGNEE_API_KEY", None)
os.environ.pop("COGNEE_SERVICE_URL", None)
