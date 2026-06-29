from pathlib import Path

from dotenv import load_dotenv

# Load the documented example config so tests use the same values as .env.example
# rather than anything hardcoded in code. override=False means a real env var
# (e.g. an integration DATABASE_URL exported before pytest) still wins.
_ENV_EXAMPLE = Path(__file__).resolve().parent.parent / ".env.example"
load_dotenv(_ENV_EXAMPLE, override=False)
