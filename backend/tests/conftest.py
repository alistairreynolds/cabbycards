import os

# Importing app.core.db constructs the async engine at import time, which needs a
# DSN. Default one here so the hermetic unit tests import cleanly without a real
# database or a .env file present. Integration tests override this.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://cabbycards:cabbycards@localhost:5433/cabbycards",
)
