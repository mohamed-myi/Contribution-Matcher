"""enhance_user_ml_models"""

from alembic import op
import sqlalchemy as sa


revision = "455e55f862ec"
down_revision = "a7c77f9efcb6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_ml_models", sa.Column("model_type", sa.String(length=50), server_default="logistic_regression"))
    op.add_column("user_ml_models", sa.Column("evaluation_metrics", sa.JSON(), nullable=True))
    op.add_column("user_ml_models", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_ml_models", "description")
    op.drop_column("user_ml_models", "evaluation_metrics")
    op.drop_column("user_ml_models", "model_type")

