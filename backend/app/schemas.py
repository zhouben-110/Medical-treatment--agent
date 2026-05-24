from sqlalchemy import Column, String, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


def generate_id():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_id)
    created_at = Column(DateTime, server_default=func.now())
    sessions = relationship("Session", back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"))
    title = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    diagnosis = Column(Text, nullable=True)
    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session", order_by="Message.timestamp")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_id)
    session_id = Column(String, ForeignKey("sessions.id"))
    role = Column(String)  # 'user' or 'assistant'
    content = Column(Text)
    timestamp = Column(DateTime, server_default=func.now())
    session = relationship("Session", back_populates="messages")


class SymptomCategory(Base):
    __tablename__ = "symptom_categories"

    id = Column(String, primary_key=True, default=generate_id)
    name = Column(String, unique=True)
    symptoms = relationship("Symptom", back_populates="category")


class Symptom(Base):
    __tablename__ = "symptoms"

    id = Column(String, primary_key=True, default=generate_id)
    category_id = Column(String, ForeignKey("symptom_categories.id"))
    name = Column(String)
    category = relationship("SymptomCategory", back_populates="symptoms")
