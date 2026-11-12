import pytest

from app.api.errors import APIError
from app.core.config import Settings
from app.services.pricing import quote


@pytest.mark.parametrize(
    "base,extra,pets,nights,subtotal,fee,total",
    [
        (5000, 2000, 2, 3, 21000, 2100, 23100),
        (5000, 2000, 1, 3, 15000, 1500, 16500),
        (5, 0, 1, 1, 5, 1, 6),
        (4, 0, 1, 1, 4, 0, 4),
        (15, 0, 1, 1, 15, 2, 17),
        (0, 0, 2, 4, 0, 0, 0),
    ],
)
def test_exact_quote(base, extra, pets, nights, subtotal, fee, total):
    result = quote(base, extra, pets, nights)
    assert (result.subtotal_cents, result.service_fee_cents, result.total_cents) == (
        subtotal,
        fee,
        total,
    )


def test_overflow_rejected():
    with pytest.raises(APIError) as error:
        quote(9007199254740991, 0, 1, 100)
    assert error.value.code == "booking_price_out_of_range"


def test_payment_window_configuration():
    assert (
        Settings(_env_file=None, app_env="test").booking_payment_window_seconds == 1800
    )
    assert (
        Settings(
            _env_file=None, app_env="test", booking_payment_window_seconds=600
        ).booking_payment_window_seconds
        == 600
    )
    with pytest.raises(ValueError):
        Settings(_env_file=None, app_env="test", booking_payment_window_seconds=0)
