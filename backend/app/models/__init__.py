from app.models.auth_identity import AuthIdentity
from app.models.base import Base
from app.models.card import Card
from app.models.deck import Deck, DeckEntry
from app.models.email_verification_token import EmailVerificationToken
from app.models.holding import Holding
from app.models.location import Location
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User

# Importing every model here ensures they are registered on Base.metadata,
# which Alembic autogenerate and create_all rely on.
__all__ = [
    "AuthIdentity",
    "Base",
    "Card",
    "Deck",
    "DeckEntry",
    "EmailVerificationToken",
    "Holding",
    "Location",
    "PasswordResetToken",
    "User",
]
