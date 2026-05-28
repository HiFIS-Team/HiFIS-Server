"""branches에 messenger_admin_id 컬럼 추가

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-28 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """안부 메시지(D+N, 만기 안내 등) 발송자로 고정될 admin 참조.

    삭제 시 SET NULL - admin이 삭제되면 지점은 살아남되 안부 메시지가 시스템 양식으로 폴백.
    """
    op.add_column(
        'branches',
        sa.Column('messenger_admin_id', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        'branches_messenger_admin_id_fkey',
        'branches', 'admins',
        ['messenger_admin_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        'branches_messenger_admin_id_fkey',
        'branches',
        type_='foreignkey',
    )
    op.drop_column('branches', 'messenger_admin_id')
