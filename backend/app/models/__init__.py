"""Import this registry to register every table with SQLAlchemy/Alembic metadata."""

from app.models.accounts import HostProfile, User
from app.models.auth import AuthSession, EmailVerificationToken
from app.models.bookings import Booking, BookingPet
from app.models.listings import Listing, ListingAcceptedSpecies
from app.models.payments import PaymentAttempt, StripeWebhookEvent
from app.models.pets import Pet

__all__ = [
    "AuthSession",
    "EmailVerificationToken",
    "Booking",
    "BookingPet",
    "HostProfile",
    "Listing",
    "ListingAcceptedSpecies",
    "Pet",
    "PaymentAttempt",
    "StripeWebhookEvent",
    "User",
]
