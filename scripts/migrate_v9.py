import logging
from sqlalchemy import create_engine, text
from backend.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    engine = create_engine(settings.DATABASE_URL)
    with engine.begin() as conn:
        logger.info("Checking database schema for progress column...")
        conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS progress INTEGER DEFAULT 0;"))
        logger.info("Successfully added progress column to jobs table.")

if __name__ == "__main__":
    migrate()
