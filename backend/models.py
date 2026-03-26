"""
Database models and session management for the iChat application.
"""
import logging
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import sessionmaker, relationship, declarative_base

from config import DATABASE_URL

# --- Database Setup ---
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _utcnow():
    return datetime.now(timezone.utc)


# --- Models ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    conversations = relationship("Conversation", back_populates="user")
    documents = relationship("DBDocument", back_populates="user")


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    start_timestamp = Column(DateTime, default=_utcnow)
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    timestamp = Column(DateTime, default=_utcnow)
    sender = Column(String)  # 'user' or 'ai'
    content = Column(Text)
    used_web_search = Column(Boolean, default=False, nullable=False)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=True)
    conversation = relationship("Conversation", back_populates="messages")
    document = relationship("DBDocument")


class DBDocument(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    content = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"))
    upload_timestamp = Column(DateTime, default=_utcnow)
    user = relationship("User", back_populates="documents")


# --- Create Tables ---
try:
    Base.metadata.create_all(bind=engine)
    logging.info("Database tables checked/created.")
except Exception as e:
    logging.error(f"Error creating database tables: {e}")


# --- Session Management ---
@contextmanager
def get_db():
    """Context manager for database sessions. Ensures proper cleanup."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
