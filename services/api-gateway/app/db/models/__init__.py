"""
SQLAlchemy models for the API Gateway.

This package contains SQLAlchemy models for the database.
"""

# Import models to register them with the SQLAlchemy metadata
from app.db.models.document import Document
from app.db.models.user import User
from app.db.models.webhook import Webhook