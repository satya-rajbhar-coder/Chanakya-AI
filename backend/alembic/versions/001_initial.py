"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2026-11-17 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', PG_UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='user'),
        sa.Column('hierarchy_level', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('party_name', sa.String(100), nullable=True),
        sa.Column('ward_no', sa.Integer(), nullable=True),
        sa.Column('assembly_no', sa.String(50), nullable=True),
        sa.Column('parliamentary_constituency', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create clients table
    op.create_table(
        'clients',
        sa.Column('id', PG_UUID(as_uuid=True), primary_key=True),
        sa.Column('code', sa.String(100), nullable=False, unique=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('database_name', sa.String(100), nullable=False, unique=True),
        sa.Column('client_identifier', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create user_clients table
    op.create_table(
        'user_clients',
        sa.Column('user_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('client_id', PG_UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', PG_UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('client_id', PG_UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=False, server_default='application/octet-stream'),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create document_assignments table
    op.create_table(
        'document_assignments',
        sa.Column('document_id', PG_UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('user_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create conversations table
    op.create_table(
        'conversations',
        sa.Column('id', PG_UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('title', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_conversations_user_updated', 'conversations', ['user_id', 'updated_at'])

    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', PG_UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', PG_UUID(as_uuid=True), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role', sa.Enum('user', 'assistant', name='message_role'), nullable=False, server_default='user'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_messages_conversation_created_id', 'messages', ['conversation_id', 'created_at', 'id'])

    # Create refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', PG_UUID(as_uuid=True), primary_key=True),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('user_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create analysis_queries table
    op.create_table(
        'analysis_queries',
        sa.Column('id', PG_UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('client_id', PG_UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('database_name', sa.String(100), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('sql', sa.Text(), nullable=False),
        sa.Column('status', sa.String(30), nullable=False, server_default='SUCCESS'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('page_size', sa.Integer(), nullable=True),
        sa.Column('planning_time_ms', sa.Numeric(12, 3), nullable=True),
        sa.Column('execution_time_ms', sa.Numeric(12, 3), nullable=True),
        sa.Column('total_time_ms', sa.Numeric(12, 3), nullable=True),
        sa.Column('query_hash', sa.String(64), nullable=True),
        sa.Column('explain_plan', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create saved_analyses table
    op.create_table(
        'saved_analyses',
        sa.Column('id', PG_UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('client_id', PG_UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('database', sa.String(100), nullable=False),
        sa.Column('sql', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create chat_analysis_queries table
    op.create_table(
        'chat_analysis_queries',
        sa.Column('id', PG_UUID(as_uuid=True), primary_key=True),
        sa.Column('message_id', PG_UUID(as_uuid=True), sa.ForeignKey('messages.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('analysis_query_id', PG_UUID(as_uuid=True), sa.ForeignKey('analysis_queries.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('chat_analysis_queries')
    op.drop_table('saved_analyses')
    op.drop_table('analysis_queries')
    op.drop_table('refresh_tokens')
    op.drop_index('ix_messages_conversation_created_id', table_name='messages')
    op.drop_table('messages')
    op.drop_index('ix_conversations_user_updated', table_name='conversations')
    op.drop_table('conversations')
    op.drop_table('document_assignments')
    op.drop_table('documents')
    op.drop_table('user_clients')
    op.drop_table('clients')
    op.drop_table('users')