"""pt_applications에 motivation · locker_pass_id · clothes_pass_id 컬럼 추가

Revision ID: f1c2a3b4d5e6
Revises: e5e1c8642507
Create Date: 2026-05-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1c2a3b4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e5e1c8642507'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """PT 신청에 락커·운동복 선택 + 방문목적(motivation) 추가."""
    op.add_column(
        'pt_applications',
        sa.Column('locker_pass_id', sa.UUID(), nullable=True),
    )
    op.add_column(
        'pt_applications',
        sa.Column('clothes_pass_id', sa.UUID(), nullable=True),
    )
    op.add_column(
        'pt_applications',
        sa.Column('motivation', sa.String(length=20), nullable=True),
    )
    op.create_foreign_key(
        'pt_applications_locker_pass_id_fkey',
        'pt_applications', 'locker_passes',
        ['locker_pass_id'], ['id'],
        ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'pt_applications_clothes_pass_id_fkey',
        'pt_applications', 'clothes_passes',
        ['clothes_pass_id'], ['id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    """롤백."""
    op.drop_constraint(
        'pt_applications_clothes_pass_id_fkey',
        'pt_applications',
        type_='foreignkey',
    )
    op.drop_constraint(
        'pt_applications_locker_pass_id_fkey',
        'pt_applications',
        type_='foreignkey',
    )
    op.drop_column('pt_applications', 'motivation')
    op.drop_column('pt_applications', 'clothes_pass_id')
    op.drop_column('pt_applications', 'locker_pass_id')
