"""Require current, affirmative, idempotent consent.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preserve legacy pilot records for inspection. They cannot satisfy the new route's
    # current-notice lookup because their notice_version is not the deployed version.
    # NOT VALID keeps historical false acknowledgements while enforcing the rule for new rows.
    op.execute(
        "ALTER TABLE consents ADD CONSTRAINT consents_ack_required "
        "CHECK (cross_border_ack = true) NOT VALID"
    )
    # A session lock makes the current-consent insert idempotent without rejecting any
    # duplicate legacy records that may already exist.


def downgrade() -> None:
    op.drop_constraint("consents_ack_required", "consents", type_="check")
