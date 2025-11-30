"""
Machine Learning related SQLAlchemy models.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User


class UserMLModel(Base):
    """
    User's personalized ML model for issue scoring.
    
    Stores trained model paths and performance metrics.
    Each user can have their own trained model based on their feedback.
    """
    __tablename__ = "user_ml_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    model_type: Mapped[str] = mapped_column(String(50), default="logistic_regression")
    model_path: Mapped[str] = mapped_column(String(512))
    scaler_path: Mapped[Optional[str]] = mapped_column(String(512))
    metrics: Mapped[Optional[Dict]] = mapped_column(JSON)
    evaluation_metrics: Mapped[Optional[Dict]] = mapped_column(JSON)
    description: Mapped[Optional[str]] = mapped_column(Text)
    trained_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="ml_models")

