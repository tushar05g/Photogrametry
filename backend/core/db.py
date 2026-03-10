from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool, QueuePool
from backend.core.config import DATABASE_URL

# 🎓 TEACHER'S NOTE: Connection pooling optimization
# For SQLite (dev): Use NullPool (no pooling, new connection each time)
# For PostgreSQL (prod): Use QueuePool (persistent connections, min_cached=5, max_overflow=10)
#
# BENEFITS OF POOLING:
# - SQLAlchemy reuses connections instead of creating new ones
# - Reduces connection overhead, especially for PostgreSQL
# - Thread-safe connection management

if DATABASE_URL.startswith("sqlite"):
    # SQLite: Use NullPool (each request gets a new connection)
    # Add check_same_thread=False for multi-threaded access
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=NullPool  # No connection pooling for SQLite
    )
else:
    # PostgreSQL: Use QueuePool for connection reuse
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=5,           # Max connections to keep in the pool
        max_overflow=10,       # Max additional connections beyond pool_size
        pool_pre_ping=True,    # Test connections before using them
        pool_recycle=3600      # Recycle connections after 1 hour
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 🎓 TEACHER'S NOTE: Dependency Injection function for FastAPI
# This opens a connection to the database for each request and closes it automatically.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
