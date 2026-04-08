"""add price_cents to listings

Revision ID: a1b2c3d4e5f6
Revises: eda605197328
Create Date: 2026-04-08 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "eda605197328"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("price_cents", sa.Integer(), nullable=True))
    op.drop_index("idx_listings_filters", table_name="listings")
    op.create_index("idx_listings_filters", "listings", ["city", "property_type", "price_cents"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_listings_filters", table_name="listings")
    op.create_index("idx_listings_filters", "listings", ["city", "property_type", "price"], unique=False)
    op.drop_column("listings", "price_cents")
