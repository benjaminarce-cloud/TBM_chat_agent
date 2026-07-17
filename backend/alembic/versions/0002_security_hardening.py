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
    # The legacy UI explicitly displayed placeholder legal copy and the API accepted
    # caller-selected versions, so no legacy record can prove acceptance of an approved notice.
    op.execute("DELETE FROM messages")
    op.execute("DELETE FROM leads")
    op.execute("DELETE FROM consents")
    op.execute("UPDATE sessions SET source = NULL")
    op.create_check_constraint("consents_ack_required", "consents", "cross_border_ack = true")
    op.create_unique_constraint(
        "uq_consents_session_notice", "consents", ["session_id", "notice_version"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_consents_session_notice", "consents", type_="unique")
    op.drop_constraint("consents_ack_required", "consents", type_="check")
