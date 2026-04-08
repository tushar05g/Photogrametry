import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ No DATABASE_URL found in .env")
    exit(1)

# Fix for postgres:// vs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def run_migration():
    print(f"🚀 Connecting to database...")
    with engine.connect() as conn:
        print("🛠️ Adding quality_report column to jobs table...")
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN quality_report JSONB;"))
            conn.commit()
            print("✅ Column added successfully!")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("⏭️ Column already exists, skipping.")
            else:
                print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_migration()
