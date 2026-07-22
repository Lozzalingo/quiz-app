"""add game timer, submission modes, media uploads, chat, round bonus

Revision ID: 0a06ac0880f1
Revises: 4be91ee661b6
Create Date: 2026-07-19 16:52:57.534187

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0a06ac0880f1'
down_revision = '4be91ee661b6'
branch_labels = None
depends_on = None


def upgrade():
    # Game model extensions
    with op.batch_alter_table('game', schema=None) as batch_op:
        batch_op.add_column(sa.Column('game_type', sa.String(length=30), nullable=False, server_default='quiz'))
        batch_op.add_column(sa.Column('timer_end_time', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('round_label', sa.String(length=50), nullable=False, server_default='Round'))
        batch_op.add_column(sa.Column('is_gallery_public', sa.Boolean(), nullable=True, server_default='false'))

    # Round model extensions
    with op.batch_alter_table('round', schema=None) as batch_op:
        batch_op.add_column(sa.Column('submission_mode', sa.String(length=20), nullable=False, server_default='all_at_once'))
        batch_op.add_column(sa.Column('bonus_thresholds_json', sa.Text(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('branching_rules_json', sa.Text(), nullable=True))

    # MediaUpload table
    op.create_table('media_upload',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('round_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.String(length=50), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('original_filename', sa.String(length=500), nullable=False),
        sa.Column('storage_key', sa.String(length=500), nullable=True),
        sa.Column('storage_url', sa.String(length=1000), nullable=True),
        sa.Column('file_type', sa.String(length=20), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('upload_status', sa.String(length=20), nullable=False, server_default='queued'),
        sa.Column('upload_progress', sa.Integer(), server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('audit_status', sa.String(length=20), nullable=False, server_default='unaudited'),
        sa.Column('audit_notes', sa.Text(), nullable=True),
        sa.Column('audited_at', sa.DateTime(), nullable=True),
        sa.Column('audited_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['team_id'], ['team.id'], ),
        sa.ForeignKeyConstraint(['round_id'], ['round.id'], ),
        sa.ForeignKeyConstraint(['game_id'], ['game.id'], ),
        sa.ForeignKeyConstraint(['audited_by'], ['admin.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # ChatMessage table
    op.create_table('chat_message',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('sender_type', sa.String(length=10), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['game_id'], ['game.id'], ),
        sa.ForeignKeyConstraint(['team_id'], ['team.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # RoundBonus table
    op.create_table('round_bonus',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('round_id', sa.Integer(), nullable=False),
        sa.Column('bonus_points', sa.Float(), server_default='0'),
        sa.Column('correct_count', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['team_id'], ['team.id'], ),
        sa.ForeignKeyConstraint(['round_id'], ['round.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'round_id', name='unique_round_bonus')
    )


def downgrade():
    op.drop_table('round_bonus')
    op.drop_table('chat_message')
    op.drop_table('media_upload')

    with op.batch_alter_table('round', schema=None) as batch_op:
        batch_op.drop_column('branching_rules_json')
        batch_op.drop_column('bonus_thresholds_json')
        batch_op.drop_column('submission_mode')

    with op.batch_alter_table('game', schema=None) as batch_op:
        batch_op.drop_column('is_gallery_public')
        batch_op.drop_column('round_label')
        batch_op.drop_column('timer_end_time')
        batch_op.drop_column('game_type')
