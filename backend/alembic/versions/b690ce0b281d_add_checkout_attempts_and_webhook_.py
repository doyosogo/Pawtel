"""add checkout attempts and webhook receipts

Revision ID: b690ce0b281d
Revises: 868589ec460a
Create Date: 2026-11-02 13:20:45.582726
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b690ce0b281d"
down_revision: str | Sequence[str] | None = "868589ec460a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reviewed: provider identity, one unresolved attempt, safe event receipts.
    op.create_table(
        "stripe_webhook_events",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("object_id", sa.String(length=255), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "result", sa.String(length=20), server_default="RECEIVED", nullable=False
        ),
        sa.CheckConstraint(
            "result IN ('RECEIVED','PROCESSED','IGNORED','REJECTED','RECONCILIATION')",
            name=op.f("ck_stripe_webhook_events_result_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stripe_webhook_events")),
    )
    op.create_index(
        op.f("ix_stripe_webhook_events_object_id"),
        "stripe_webhook_events",
        ["object_id"],
        unique=False,
    )
    op.create_table(
        "payment_attempts",
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider", sa.String(length=10), server_default="stripe", nullable=False
        ),
        sa.Column(
            "status", sa.String(length=30), server_default="CREATING", nullable=False
        ),
        sa.Column("checkout_session_id", sa.String(length=255), nullable=True),
        sa.Column("payment_intent_id", sa.String(length=255), nullable=True),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("subtotal_cents", sa.BigInteger(), nullable=False),
        sa.Column("service_fee_cents", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency", sa.String(length=3), server_default="aud", nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("return_url", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciliation_reason", sa.String(length=80), nullable=True),
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
            "currency = 'aud'", name=op.f("ck_payment_attempts_currency_aud")
        ),
        sa.CheckConstraint(
            "provider = 'stripe'", name=op.f("ck_payment_attempts_provider_stripe")
        ),
        sa.CheckConstraint(
            "status IN ('CREATING','OPEN','SUCCEEDED','EXPIRED','FAILED',"
            "'CANCELLED','REQUIRES_RECONCILIATION')",
            name=op.f("ck_payment_attempts_status_valid"),
        ),
        sa.CheckConstraint(
            "amount_cents = subtotal_cents + service_fee_cents",
            name=op.f("ck_payment_attempts_amount_matches_parts"),
        ),
        sa.CheckConstraint(
            "amount_cents >= 0 AND subtotal_cents >= 0 AND service_fee_cents >= 0",
            name=op.f("ck_payment_attempts_amounts_nonnegative"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_payment_attempts_expiry_ordered")
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_payment_attempts_booking_id_bookings"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_attempts")),
        sa.UniqueConstraint(
            "checkout_session_id", name=op.f("uq_payment_attempts_checkout_session_id")
        ),
        sa.UniqueConstraint(
            "payment_intent_id", name=op.f("uq_payment_attempts_payment_intent_id")
        ),
    )
    op.create_index(
        op.f("ix_payment_attempts_booking_id"),
        "payment_attempts",
        ["booking_id"],
        unique=False,
    )
    op.create_index(
        "uq_payment_attempt_active_booking",
        "payment_attempts",
        ["booking_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('CREATING','OPEN','REQUIRES_RECONCILIATION')"
        ),
    )


def downgrade() -> None:
    # Reviewed: provider identity, one unresolved attempt, safe event receipts.
    op.drop_index(
        "uq_payment_attempt_active_booking",
        table_name="payment_attempts",
        postgresql_where=sa.text(
            "status IN ('CREATING','OPEN','REQUIRES_RECONCILIATION')"
        ),
    )
    op.drop_index(op.f("ix_payment_attempts_booking_id"), table_name="payment_attempts")
    op.drop_table("payment_attempts")
    op.drop_index(
        op.f("ix_stripe_webhook_events_object_id"), table_name="stripe_webhook_events"
    )
    op.drop_table("stripe_webhook_events")
