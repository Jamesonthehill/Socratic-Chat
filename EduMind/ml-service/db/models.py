from sqlalchemy import Column, String, Text, DateTime, Enum, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    project_id = Column(String(36), nullable=False)
    topic = Column(String(255))
    memory_state = Column(JSON)
    # created_at, last_active_at already exist

class GraphRunSession(Base):
    __tablename__ = "graph_runs"

    id            = Column(String(36), primary_key=True)
    project_id      = Column(String(36), nullable=False)
    status        = Column(
        Enum("pending", "processing", "completed", "failed", name="graph_run_status"),
        nullable=False,
        server_default="pending",
    )
    created_at    = Column(DateTime, nullable=False, server_default=func.now())
    completed_at  = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)