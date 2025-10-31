"""Add ScanJob table and is_premium flag on user

Revision ID: a1b2c3d4e5f6
Revises: 1a31ce608336
Create Date: 2025-10-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "1a31ce608336"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_premium to user
    op.add_column("user", sa.Column("is_premium", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    # Create scan_job table
    op.create_table(
        "scanjob",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False, index=True),
        sa.Column("status", sa.String(length=64), nullable=False, index=True),
        sa.Column("step", sa.String(length=32), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("teaser_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("full_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("scanjob")
    op.drop_column("user", "is_premium")
