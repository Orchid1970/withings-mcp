from datetime import datetime
from sqlalchemy import String, Text, DateTime, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base

class TokenRecord(Base):
    __tablename__ = "tokens"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Observation(Base):
    __tablename__ = "observations"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    resource_type: Mapped[str] = mapped_column(String(50), default="Observation")
    status: Mapped[str] = mapped_column(String(20), default="final")
    code_system: Mapped[str] = mapped_column(String(255))
    code_value: Mapped[str] = mapped_column(String(50))
    code_display: Mapped[str] = mapped_column(String(255))
    value_quantity: Mapped[float] = mapped_column(Float, nullable=True)
    value_unit: Mapped[str] = mapped_column(String(50), nullable=True)
    effective_datetime: Mapped[datetime] = mapped_column(DateTime)
    withings_type: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)