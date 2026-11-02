"""Exact AUD cent quotes; immutable once persisted on a request."""

from dataclasses import dataclass

from app.api.errors import APIError

MAX_JSON_INTEGER = 9007199254740991


@dataclass(frozen=True)
class Quote:
    nightly_base_price_cents: int
    additional_pet_price_cents: int
    subtotal_cents: int
    service_fee_cents: int
    total_cents: int


def quote(base: int, additional: int, pets: int, nights: int) -> Quote:
    if base < 0 or additional < 0 or pets < 1 or nights < 1:
        raise ValueError("Invalid pricing inputs.")
    subtotal = nights * (base + additional * (pets - 1))
    # For nonnegative integer cents, rounding subtotal/10 HALF-UP is exact here.
    fee = (subtotal + 5) // 10
    total = subtotal + fee
    if max(base, additional, total) > MAX_JSON_INTEGER:
        raise APIError(422, "booking_price_out_of_range", "Booking quote is too large.")
    return Quote(base, additional, subtotal, fee, total)
