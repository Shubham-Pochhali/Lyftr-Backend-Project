from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Text

Base = declarative_base()


class Message(Base):
    __tablename__ = "messages"

    message_id = Column(String, primary_key=True)
    from_msisdn = Column(String, nullable=False)
    to_msisdn = Column(String, nullable=False)
    ts = Column(String, nullable=False)        # ISO-8601 UTC string
    text = Column(Text, nullable=True)
    created_at = Column(String, nullable=False)  # server time ISO-8601
