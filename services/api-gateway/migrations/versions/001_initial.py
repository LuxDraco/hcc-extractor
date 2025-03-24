"""Initial database schema

Revision ID: 001_initial
Revises:
Create Date: 2025-03-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, default=False),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(),
                  onupdate=sa.func.now()),
    )

    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=False),
        sa.Column('storage_type', sa.Enum('LOCAL', 'S3', 'GCS', name='storagetype'), nullable=False),
        sa.Column('storage_path', sa.String(500), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'EXTRACTING', 'ANALYZING', 'VALIDATING', 'COMPLETED', 'FAILED',
                                    name='processingstatus'), nullable=False, default='PENDING'),
        sa.Column('is_processed', sa.Boolean(), nullable=False, default=False),
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_conditions', sa.Integer(), nullable=True),
        sa.Column('hcc_relevant_conditions', sa.Integer(), nullable=True),
        sa.Column('extraction_result_path', sa.String(500), nullable=True),
        sa.Column('analysis_result_path', sa.String(500), nullable=True),
        sa.Column('validation_result_path', sa.String(500), nullable=True),
        sa.Column('errors', sa.Text(), nullable=True),
        sa.Column('patient_info', postgresql.JSONB(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, default={}),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(),
                  onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )

    # Create webhooks table
    op.create_table(
        'webhooks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('event_types', postgresql.JSONB(), nullable=False, default=[]),
        sa.Column('status', sa.Enum('ACTIVE', 'DISABLED', 'SUSPENDED', name='webhookstatus'), nullable=False,
                  default='ACTIVE'),
        sa.Column('secret_key', sa.String(255), nullable=True),
        sa.Column('headers', postgresql.JSONB(), nullable=False, default={}),
        sa.Column('max_attempts', sa.Integer(), nullable=False, default=3),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, default=10),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_failure_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('success_count', sa.Integer(), nullable=False, default=0),
        sa.Column('failure_count', sa.Integer(), nullable=False, default=0),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(),
                  onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )

    # Create indexes
    op.create_index('ix_documents_status', 'documents', ['status'], unique=False)
    op.create_index('ix_documents_user_id', 'documents', ['user_id'], unique=False)
    op.create_index('ix_webhooks_user_id', 'webhooks', ['user_id'], unique=False)
    op.create_index('ix_webhooks_status', 'webhooks', ['status'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('webhooks')
    op.drop_table('documents')
    op.drop_table('users')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS webhookstatus")
    op.execute("DROP TYPE IF EXISTS processingstatus")
    op.execute("DROP TYPE IF EXISTS storagetype")