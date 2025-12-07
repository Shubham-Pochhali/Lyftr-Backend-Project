from typing import Iterable, Optional, Tuple, List

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from .config import settings
from .models import Base, Message


def _engine_connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_engine_connect_args(settings.DATABASE_URL),
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Iterable[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def insert_message(
    db: Session,
    *,
    message_id: str,
    from_msisdn: str,
    to_msisdn: str,
    ts: str,
    text: Optional[str],
    created_at: str,
) -> Tuple[Message | None, bool]:
    """
    Returns (message, duplicate_flag).
    duplicate_flag=True if the message_id already existed.
    """
    msg = Message(
        message_id=message_id,
        from_msisdn=from_msisdn,
        to_msisdn=to_msisdn,
        ts=ts,
        text=text,
        created_at=created_at,
    )
    db.add(msg)
    try:
        db.commit()
        db.refresh(msg)
        return msg, False
    except IntegrityError:
        db.rollback()
        # Already exists -> idempotent behaviour
        existing = db.query(Message).filter(Message.message_id == message_id).first()
        return existing, True


def list_messages(
    db: Session,
    *,
    limit: int,
    offset: int,
    from_msisdn: Optional[str] = None,
    since_ts: Optional[str] = None,
    q: Optional[str] = None,
) -> Tuple[List[Message], int]:
    query = db.query(Message)

    if from_msisdn:
        query = query.filter(Message.from_msisdn == from_msisdn)

    if since_ts:
        # string compare is ok for ISO-8601
        query = query.filter(Message.ts >= since_ts)

    if q:
        like = f"%{q.lower()}%"
        query = query.filter(func.lower(Message.text).like(like))

    total = query.count()

    rows = (
        query.order_by(Message.ts.asc(), Message.message_id.asc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return rows, total


def get_stats(db: Session) -> dict:
    total_messages = db.query(func.count(Message.message_id)).scalar() or 0
    senders_count = db.query(func.count(func.distinct(Message.from_msisdn))).scalar() or 0

    # top 10 senders
    rows = (
        db.query(Message.from_msisdn, func.count(Message.message_id).label("cnt"))
        .group_by(Message.from_msisdn)
        .order_by(func.count(Message.message_id).desc())
        .limit(10)
        .all()
    )
    messages_per_sender = [
        {"from": r[0], "count": int(r[1])} for r in rows
    ]

    first_ts = db.query(func.min(Message.ts)).scalar()
    last_ts = db.query(func.max(Message.ts)).scalar()

    return {
        "total_messages": int(total_messages),
        "senders_count": int(senders_count),
        "messages_per_sender": messages_per_sender,
        "first_message_ts": first_ts,
        "last_message_ts": last_ts,
    }
