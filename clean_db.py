from backend.core.db import engine, Base
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def nuclear_drop():
    with engine.connect() as conn:
        logger.info("🗑️ Nuclear drop of all tables...")
        # Drop with cascade
        conn.execute(text("DROP TABLE IF EXISTS stages CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS jobs CASCADE;"))
        # Drop enums if they exist
        conn.execute(text("DROP TYPE IF EXISTS jobstatus CASCADE;"))
        conn.execute(text("DROP TYPE IF EXISTS jobstage CASCADE;"))
        conn.execute(text("DROP TYPE IF EXISTS stagestatus CASCADE;"))
        conn.commit()
        logger.info("✅ Dropped everything.")

    logger.info("🛠️ Recreating tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database recreated successfully.")

if __name__ == "__main__":
    nuclear_drop()
