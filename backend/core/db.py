from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool, QueuePool
from backend.config import settings

# 🎓 Connection pooling optimization
# For SQLite (dev): Use NullPool (no pooling, new connection each time)
# For PostgreSQL (prod): Use QueuePool (persistent connections)

engine_kwargs = {
    "connect_args": {},
    "pool_pre_ping": True
}

if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"]["check_same_thread"] = False
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["poolclass"] = QueuePool
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(
    settings.DATABASE_URL,
    **engine_kwargs
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
