"""notifications + push_subscriptions 테이블 추가

Revision ID: a8c9d0e1f2g3
Revises: f1c2a3b4d5e6
Create Date: 2026-05-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8c9d0e1f2g3'
down_revision: Union[str, Sequence[str], None] = 'f1c2a3b4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """어드민 알림(DB) + Web Push 구독 테이블 추가."""
    # notifications: 어드민별 알림 한 행씩 (admin_id, is_read, created_at 복합 인덱스)
    op.create_table(
        'notifications',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('admin_id', sa.UUID(), nullable=False),
        sa.Column('source_type', sa.String(length=20), nullable=False),
        sa.Column('source_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column(
            'is_read', sa.Boolean(),
            server_default='false', nullable=False,
        ),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['admin_id'], ['admins.id'], ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_notifications_admin_read_created',
        'notifications',
        ['admin_id', 'is_read', 'created_at'],
    )

    # push_subscriptions: 어드민 1명이 N개 기기 (endpoint unique)
    op.create_table(
        'push_subscriptions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('admin_id', sa.UUID(), nullable=False),
        sa.Column('endpoint', sa.String(length=500), nullable=False),
        sa.Column('p256dh', sa.String(length=200), nullable=False),
        sa.Column('auth', sa.String(length=100), nullable=False),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['admin_id'], ['admins.id'], ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('endpoint'),
    )
    op.create_index(
        'ix_push_subscriptions_admin_id',
        'push_subscriptions',
        ['admin_id'],
    )


def downgrade() -> None:
    """롤백."""
    op.drop_index(
        'ix_push_subscriptions_admin_id', table_name='push_subscriptions',
    )
    op.drop_table('push_subscriptions')
    op.drop_index(
        'ix_notifications_admin_read_created', table_name='notifications',
    )
    op.drop_table('notifications')
