"""Remove clients and user_clients tables, remove client_id from documents, analysis_queries, saved_analyses

Revision ID: 002
Revises: 001
Create Date: 2026-11-19 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add corporation column to users table
    op.add_column('users', sa.Column('corporation', sa.String(100), nullable=True))
    
    # Drop foreign key constraints first
    op.drop_constraint('documents_client_id_fkey', 'documents', type_='foreignkey')
    op.drop_constraint('analysis_queries_client_id_fkey', 'analysis_queries', type_='foreignkey')
    op.drop_constraint('saved_analyses_client_id_fkey', 'saved_analyses', type_='foreignkey')
    
    # Drop client_id columns
    op.drop_column('documents', 'client_id')
    op.drop_column('analysis_queries', 'client_id')
    op.drop_column('saved_analyses', 'client_id')
    
    # Drop user_clients table
    op.drop_table('user_clients')
    
    # Drop clients table
    op.drop_table('clients')


def downgrade() -> None:
    # Remove corporation column from users table
    op.drop_column('users', 'corporation')
    
    # Recreate clients table
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
    
    # Recreate user_clients table
    op.create_table(
        'user_clients',
        sa.Column('user_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('client_id', PG_UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # Add client_id columns back
    op.add_column('documents', sa.Column('client_id', PG_UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='SET NULL'), nullable=True, index=True))
    op.add_column('analysis_queries', sa.Column('client_id', PG_UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='SET NULL'), nullable=True, index=True))
    op.add_column('saved_analyses', sa.Column('client_id', PG_UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='SET NULL'), nullable=True, index=True))
    
    # Recreate foreign key constraints
    op.create_foreign_key('documents_client_id_fkey', 'documents', 'clients', ['client_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('analysis_queries_client_id_fkey', 'analysis_queries', 'clients', ['client_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('saved_analyses_client_id_fkey', 'saved_analyses', 'clients', ['client_id'], ['id'], ondelete='SET NULL')