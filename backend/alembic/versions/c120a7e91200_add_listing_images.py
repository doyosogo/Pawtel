"""Add tracked Listing media metadata, never raw image bytes.

Revision ID: c120a7e91200
Revises: b690ce0b281d
"""

import sqlalchemy as sa

from alembic import op

revision = "c120a7e91200"
down_revision = "b690ce0b281d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "listing_images",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("public_id", sa.String(255), nullable=False),
        sa.Column("url", sa.String(600), nullable=False),
        sa.Column("alt_text", sa.String(160), server_default="", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(20), server_default="UPLOADING", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_listing_images")),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listings.id"],
            ondelete="RESTRICT",
            name=op.f("fk_listing_images_listing_id_listings"),
        ),
        sa.UniqueConstraint("public_id", name=op.f("uq_listing_images_public_id")),
        sa.CheckConstraint(
            "status IN ('UPLOADING','READY','DELETE_PENDING')",
            name=op.f("ck_listing_images_status_valid"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0", name=op.f("ck_listing_images_sort_nonnegative")
        ),
    )
    op.create_index(
        op.f("ix_listing_images_listing_id"), "listing_images", ["listing_id"]
    )


def downgrade():
    op.drop_index(op.f("ix_listing_images_listing_id"), table_name="listing_images")
    op.drop_table("listing_images")
