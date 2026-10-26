"""create boarding marketplace relational schema

Revision ID: 6667e668c806
Revises: (initial revision)
Create Date: 2026-10-26 13:45:59.623235
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "6667e668c806"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Explicit ownership avoids creating shared pet_species twice and drops all
# native enum types on downgrade. Migration definitions are independent of models.
pet_species = postgresql.ENUM("DOG", "CAT", name="pet_species", create_type=False)
australian_state = postgresql.ENUM(
    "ACT",
    "NSW",
    "NT",
    "QLD",
    "SA",
    "TAS",
    "VIC",
    "WA",
    name="australian_state",
    create_type=False,
)
listing_status = postgresql.ENUM(
    "DRAFT", "PUBLISHED", "ARCHIVED", name="listing_status", create_type=False
)
booking_status = postgresql.ENUM(
    "REQUESTED",
    "DECLINED",
    "AWAITING_PAYMENT",
    "CONFIRMED",
    "PAYMENT_FAILED",
    "CANCELLED",
    "COMPLETED",
    "EXPIRED",
    name="booking_status",
    create_type=False,
)


def upgrade() -> None:
    for enum_type in (pet_species, australian_state, listing_status, booking_status):
        enum_type.create(op.get_bind(), checkfirst=False)

    op.create_table(
        "users",
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "btrim(display_name) <> ''", name=op.f("ck_users_display_name_not_blank")
        ),
        sa.CheckConstraint(
            "email = lower(btrim(email)) AND email <> '' AND email !~ '[[:space:]]'",
            name=op.f("ck_users_email_normalized"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "host_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_host_profiles_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_host_profiles")),
    )
    op.create_table(
        "pets",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("species", pet_species, nullable=False),
        sa.Column("breed", sa.String(length=100), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("btrim(name) <> ''", name=op.f("ck_pets_name_not_blank")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_pets_owner_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pets")),
    )
    op.create_index(op.f("ix_pets_owner_id"), "pets", ["owner_id"], unique=False)
    op.create_table(
        "listings",
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("suburb", sa.String(length=100), nullable=False),
        sa.Column("state", australian_state, nullable=False),
        sa.Column("postcode", sa.String(length=4), nullable=False),
        sa.Column(
            "country_code", sa.String(length=2), server_default="AU", nullable=False
        ),
        sa.Column("max_pet_capacity", sa.Integer(), nullable=False),
        sa.Column("base_nightly_price_cents", sa.BigInteger(), nullable=False),
        sa.Column("additional_pet_price_cents", sa.BigInteger(), nullable=False),
        sa.Column("status", listing_status, server_default="DRAFT", nullable=False),
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "btrim(suburb) <> ''", name=op.f("ck_listings_suburb_not_blank")
        ),
        sa.CheckConstraint(
            "btrim(title) <> ''", name=op.f("ck_listings_title_not_blank")
        ),
        sa.CheckConstraint(
            "country_code = 'AU'", name=op.f("ck_listings_country_australia")
        ),
        sa.CheckConstraint(
            "postcode ~ '^[0-9]{4}$'", name=op.f("ck_listings_postcode_format")
        ),
        sa.CheckConstraint(
            "additional_pet_price_cents >= 0",
            name=op.f("ck_listings_extra_price_nonnegative"),
        ),
        sa.CheckConstraint(
            "base_nightly_price_cents >= 0",
            name=op.f("ck_listings_base_price_nonnegative"),
        ),
        sa.CheckConstraint(
            "max_pet_capacity > 0", name=op.f("ck_listings_capacity_positive")
        ),
        sa.ForeignKeyConstraint(
            ["host_id"],
            ["host_profiles.user_id"],
            name=op.f("fk_listings_host_id_host_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_listings")),
    )
    op.create_index(op.f("ix_listings_host_id"), "listings", ["host_id"], unique=False)
    op.create_table(
        "bookings",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", booking_status, server_default="REQUESTED", nullable=False),
        sa.Column("payment_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nightly_base_price_cents", sa.BigInteger(), nullable=False),
        sa.Column("additional_pet_price_cents", sa.BigInteger(), nullable=False),
        sa.Column("subtotal_cents", sa.BigInteger(), nullable=False),
        sa.Column("service_fee_cents", sa.BigInteger(), nullable=False),
        sa.Column("total_cents", sa.BigInteger(), nullable=False),
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status <> 'AWAITING_PAYMENT' OR payment_expires_at IS NOT NULL",
            name=op.f("ck_bookings_payment_hold_has_deadline"),
        ),
        sa.CheckConstraint(
            "additional_pet_price_cents >= 0",
            name=op.f("ck_bookings_extra_price_nonnegative"),
        ),
        sa.CheckConstraint(
            "end_date > start_date", name=op.f("ck_bookings_dates_ordered")
        ),
        sa.CheckConstraint(
            "nightly_base_price_cents >= 0",
            name=op.f("ck_bookings_base_price_nonnegative"),
        ),
        sa.CheckConstraint(
            "service_fee_cents >= 0", name=op.f("ck_bookings_fee_nonnegative")
        ),
        sa.CheckConstraint(
            "subtotal_cents >= 0", name=op.f("ck_bookings_subtotal_nonnegative")
        ),
        sa.CheckConstraint(
            "total_cents = subtotal_cents + service_fee_cents",
            name=op.f("ck_bookings_total_matches_parts"),
        ),
        sa.CheckConstraint(
            "total_cents >= 0", name=op.f("ck_bookings_total_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listings.id"],
            name=op.f("fk_bookings_listing_id_listings"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_bookings_owner_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bookings")),
    )
    op.create_index(
        "ix_bookings_listing_status_dates",
        "bookings",
        ["listing_id", "status", "start_date", "end_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bookings_owner_id"), "bookings", ["owner_id"], unique=False
    )
    op.create_table(
        "listing_accepted_species",
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("species", pet_species, nullable=False),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listings.id"],
            name=op.f("fk_listing_accepted_species_listing_id_listings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "listing_id", "species", name=op.f("pk_listing_accepted_species")
        ),
    )
    op.create_table(
        "booking_pets",
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_booking_pets_booking_id_bookings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pet_id"],
            ["pets.id"],
            name=op.f("fk_booking_pets_pet_id_pets"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("booking_id", "pet_id", name=op.f("pk_booking_pets")),
    )
    op.create_index("ix_booking_pets_pet_id", "booking_pets", ["pet_id"], unique=False)


def downgrade() -> None:

    op.drop_index("ix_booking_pets_pet_id", table_name="booking_pets")
    op.drop_table("booking_pets")
    op.drop_table("listing_accepted_species")
    op.drop_index(op.f("ix_bookings_owner_id"), table_name="bookings")
    op.drop_index("ix_bookings_listing_status_dates", table_name="bookings")
    op.drop_table("bookings")
    op.drop_index(op.f("ix_listings_host_id"), table_name="listings")
    op.drop_table("listings")
    op.drop_index(op.f("ix_pets_owner_id"), table_name="pets")
    op.drop_table("pets")
    op.drop_table("host_profiles")
    op.drop_table("users")

    for enum_type in (booking_status, listing_status, australian_state, pet_species):
        enum_type.drop(op.get_bind(), checkfirst=False)
