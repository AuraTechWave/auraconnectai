"""add_feedback_and_reviews_tables

Revision ID: 20250729_1900_add_feedback_and_reviews_tables
Revises: 20250728_0130_0016_create_menu_versioning_tables
Create Date: 2025-07-29 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '20250729_1900_add_feedback_and_reviews_tables'
down_revision = '20250728_0130_0016_create_menu_versioning_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types
    op.execute("CREATE TYPE reviewtype AS ENUM ('product', 'service', 'order')")
    op.execute("CREATE TYPE reviewstatus AS ENUM ('pending', 'approved', 'rejected', 'hidden', 'spam')")
    op.execute("CREATE TYPE reviewsource AS ENUM ('website', 'mobile_app', 'email', 'sms', 'phone', 'in_store')")
    op.execute("CREATE TYPE sentimentscore AS ENUM ('very_negative', 'negative', 'neutral', 'positive', 'very_positive')")
    op.execute("CREATE TYPE feedbacktype AS ENUM ('complaint', 'suggestion', 'compliment', 'bug_report', 'feature_request', 'other')")
    op.execute("CREATE TYPE feedbackstatus AS ENUM ('new', 'assigned', 'in_progress', 'resolved', 'closed', 'escalated')")
    op.execute("CREATE TYPE feedbackpriority AS ENUM ('low', 'medium', 'high', 'urgent')")

    # Create reviews table
    op.create_table('reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('review_type', postgresql.ENUM('product', 'service', 'order', name='reviewtype'), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('service_id', sa.Integer(), nullable=True),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('rating', sa.Float(), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'approved', 'rejected', 'hidden', 'spam', name='reviewstatus'), nullable=False),
        sa.Column('is_anonymous', sa.Boolean(), nullable=False),
        sa.Column('reviewer_name', sa.String(length=100), nullable=True),
        sa.Column('is_verified_purchase', sa.Boolean(), nullable=False),
        sa.Column('source', postgresql.ENUM('website', 'mobile_app', 'email', 'sms', 'phone', 'in_store', name='reviewsource'), nullable=False),
        sa.Column('helpful_votes', sa.Integer(), nullable=False),
        sa.Column('not_helpful_votes', sa.Integer(), nullable=False),
        sa.Column('total_votes', sa.Integer(), nullable=False),
        sa.Column('helpful_percentage', sa.Float(), nullable=True),
        sa.Column('sentiment_score', postgresql.ENUM('very_negative', 'negative', 'neutral', 'positive', 'very_positive', name='sentimentscore'), nullable=True),
        sa.Column('sentiment_confidence', sa.Float(), nullable=True),
        sa.Column('sentiment_analysis_data', sa.JSON(), nullable=True),
        sa.Column('has_images', sa.Boolean(), nullable=False),
        sa.Column('has_videos', sa.Boolean(), nullable=False),
        sa.Column('media_count', sa.Integer(), nullable=False),
        sa.Column('has_business_response', sa.Boolean(), nullable=False),
        sa.Column('business_response_at', sa.DateTime(), nullable=True),
        sa.Column('is_featured', sa.Boolean(), nullable=False),
        sa.Column('featured_at', sa.DateTime(), nullable=True),
        sa.Column('moderated_by', sa.Integer(), nullable=True),
        sa.Column('moderated_at', sa.DateTime(), nullable=True),
        sa.Column('moderation_notes', sa.Text(), nullable=True),
        sa.Column('review_metadata', sa.JSON(), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_reviews_uuid', 'reviews', ['uuid'], unique=True)
    op.create_index('ix_reviews_customer_id', 'reviews', ['customer_id'])
    op.create_index('ix_reviews_product_id', 'reviews', ['product_id'])
    op.create_index('ix_reviews_status', 'reviews', ['status'])
    op.create_index('ix_reviews_rating', 'reviews', ['rating'])
    op.create_index('ix_reviews_created_at', 'reviews', ['created_at'])

    # Create feedback table
    op.create_table('feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('feedback_type', postgresql.ENUM('complaint', 'suggestion', 'compliment', 'bug_report', 'feature_request', 'other', name='feedbacktype'), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('customer_email', sa.String(length=255), nullable=True),
        sa.Column('customer_name', sa.String(length=100), nullable=True),
        sa.Column('customer_phone', sa.String(length=20), nullable=True),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('subcategory', sa.String(length=100), nullable=True),
        sa.Column('priority', postgresql.ENUM('low', 'medium', 'high', 'urgent', name='feedbackpriority'), nullable=False),
        sa.Column('status', postgresql.ENUM('new', 'assigned', 'in_progress', 'resolved', 'closed', 'escalated', name='feedbackstatus'), nullable=False),
        sa.Column('assigned_to', sa.Integer(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('escalated_to', sa.Integer(), nullable=True),
        sa.Column('escalated_at', sa.DateTime(), nullable=True),
        sa.Column('escalation_reason', sa.Text(), nullable=True),
        sa.Column('source', postgresql.ENUM('website', 'mobile_app', 'email', 'sms', 'phone', 'in_store', name='reviewsource'), nullable=False),
        sa.Column('sentiment_score', postgresql.ENUM('very_negative', 'negative', 'neutral', 'positive', 'very_positive', name='sentimentscore'), nullable=True),
        sa.Column('sentiment_confidence', sa.Float(), nullable=True),
        sa.Column('sentiment_analysis_data', sa.JSON(), nullable=True),
        sa.Column('auto_categorized', sa.Boolean(), nullable=False),
        sa.Column('follow_up_required', sa.Boolean(), nullable=False),
        sa.Column('follow_up_date', sa.Date(), nullable=True),
        sa.Column('response_metadata', sa.JSON(), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_feedback_uuid', 'feedback', ['uuid'], unique=True)
    op.create_index('ix_feedback_customer_id', 'feedback', ['customer_id'])
    op.create_index('ix_feedback_type', 'feedback', ['feedback_type'])
    op.create_index('ix_feedback_status', 'feedback', ['status'])
    op.create_index('ix_feedback_priority', 'feedback', ['priority'])
    op.create_index('ix_feedback_created_at', 'feedback', ['created_at'])

    # Create review_media table
    op.create_table('review_media',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('review_id', sa.Integer(), nullable=False),
        sa.Column('media_type', sa.String(length=50), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('alt_text', sa.String(length=255), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('is_processed', sa.Boolean(), nullable=False),
        sa.Column('processing_status', sa.String(length=50), nullable=True),
        sa.Column('processing_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['review_id'], ['reviews.id'], ondelete='CASCADE')
    )
    op.create_index('ix_review_media_review_id', 'review_media', ['review_id'])

    # Create review_votes table
    op.create_table('review_votes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('review_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('is_helpful', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['review_id'], ['reviews.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('review_id', 'customer_id')
    )

    # Create business_responses table
    op.create_table('business_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('review_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('responder_name', sa.String(length=100), nullable=False),
        sa.Column('responder_title', sa.String(length=100), nullable=True),
        sa.Column('responder_id', sa.Integer(), nullable=True),
        sa.Column('is_published', sa.Boolean(), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('response_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['review_id'], ['reviews.id'], ondelete='CASCADE')
    )

    # Create feedback_responses table
    op.create_table('feedback_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('feedback_id', sa.Integer(), nullable=False),
        sa.Column('responder_id', sa.Integer(), nullable=False),
        sa.Column('responder_name', sa.String(length=100), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_internal', sa.Boolean(), nullable=False),
        sa.Column('is_resolution', sa.Boolean(), nullable=False),
        sa.Column('response_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['feedback_id'], ['feedback.id'], ondelete='CASCADE')
    )

    # Create feedback_categories table
    op.create_table('feedback_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('auto_assign_keywords', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('auto_escalate', sa.Boolean(), nullable=False),
        sa.Column('escalation_priority', postgresql.ENUM('low', 'medium', 'high', 'urgent', name='feedbackpriority'), nullable=True),
        sa.Column('escalation_conditions', sa.JSON(), nullable=True),
        sa.Column('response_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create review_aggregates table
    op.create_table('review_aggregates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('total_reviews', sa.Integer(), nullable=False),
        sa.Column('average_rating', sa.Float(), nullable=False),
        sa.Column('rating_1_count', sa.Integer(), nullable=False),
        sa.Column('rating_2_count', sa.Integer(), nullable=False),
        sa.Column('rating_3_count', sa.Integer(), nullable=False),
        sa.Column('rating_4_count', sa.Integer(), nullable=False),
        sa.Column('rating_5_count', sa.Integer(), nullable=False),
        sa.Column('verified_reviews_count', sa.Integer(), nullable=False),
        sa.Column('featured_reviews_count', sa.Integer(), nullable=False),
        sa.Column('with_images_count', sa.Integer(), nullable=False),
        sa.Column('with_videos_count', sa.Integer(), nullable=False),
        sa.Column('positive_sentiment_count', sa.Integer(), nullable=False),
        sa.Column('negative_sentiment_count', sa.Integer(), nullable=False),
        sa.Column('neutral_sentiment_count', sa.Integer(), nullable=False),
        sa.Column('last_review_date', sa.DateTime(), nullable=True),
        sa.Column('trending_score', sa.Float(), nullable=True),
        sa.Column('response_metadata', sa.JSON(), nullable=True),
        sa.Column('last_calculated_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'entity_id')
    )

    # Create review_templates table
    op.create_table('review_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('review_type', postgresql.ENUM('product', 'service', 'order', name='reviewtype'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('custom_questions', sa.JSON(), nullable=True),
        sa.Column('rating_labels', sa.JSON(), nullable=True),
        sa.Column('requires_purchase', sa.Boolean(), nullable=False),
        sa.Column('allows_anonymous', sa.Boolean(), nullable=False),
        sa.Column('allows_media', sa.Boolean(), nullable=False),
        sa.Column('max_media_files', sa.Integer(), nullable=True),
        sa.Column('auto_request_after_days', sa.Integer(), nullable=True),
        sa.Column('reminder_enabled', sa.Boolean(), nullable=False),
        sa.Column('reminder_days', sa.Integer(), nullable=True),
        sa.Column('response_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create review_invitations table
    op.create_table('review_invitations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('customer_email', sa.String(length=255), nullable=False),
        sa.Column('review_type', postgresql.ENUM('product', 'service', 'order', name='reviewtype'), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('template_id', sa.Integer(), nullable=True),
        sa.Column('invitation_token', sa.String(length=255), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('opened_at', sa.DateTime(), nullable=True),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.Column('review_id', sa.Integer(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('reminder_sent_at', sa.DateTime(), nullable=True),
        sa.Column('response_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['review_id'], ['reviews.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['template_id'], ['review_templates.id'], ondelete='SET NULL')
    )
    op.create_index('ix_review_invitations_token', 'review_invitations', ['invitation_token'], unique=True)


def downgrade():
    # Drop tables in reverse order
    op.drop_table('review_invitations')
    op.drop_table('review_templates')
    op.drop_table('review_aggregates')
    op.drop_table('feedback_categories')
    op.drop_table('feedback_responses')
    op.drop_table('business_responses')
    op.drop_table('review_votes')
    op.drop_table('review_media')
    op.drop_table('feedback')
    op.drop_table('reviews')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS feedbackpriority")
    op.execute("DROP TYPE IF EXISTS feedbackstatus")
    op.execute("DROP TYPE IF EXISTS feedbacktype")
    op.execute("DROP TYPE IF EXISTS sentimentscore")
    op.execute("DROP TYPE IF EXISTS reviewsource")
    op.execute("DROP TYPE IF EXISTS reviewstatus")
    op.execute("DROP TYPE IF EXISTS reviewtype")