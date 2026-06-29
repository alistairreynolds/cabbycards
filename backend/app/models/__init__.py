from app.models.auth_identity import AuthIdentity
from app.models.base import Base
from app.models.card import Card
from app.models.collection import CollectionEntry
from app.models.deck import Deck, DeckCard
from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User

# Importing every model here ensures they are registered on Base.metadata,
# which Alembic autogenerate and create_all rely on.
__all__ = [
    "AuthIdentity",
    "Base",
    "Card",
    "CollectionEntry",
    "Deck",
    "DeckCard",
    "EmailVerificationToken",
    "User",
]
