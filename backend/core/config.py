import os
from dotenv import load_dotenv

load_dotenv()  # This reads your .env file and loads all the KEY=VALUE pairs into the environment

# 🎓 TEACHER'S NOTE: For development, we use SQLite if no DATABASE_URL is provided.
# SQLite is a file-based database that doesn't require a server, making it perfect for local testing.
# In production, you'd use PostgreSQL (like Neon or Supabase) for better performance and concurrency.
DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///./scanner.db"

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
REDIS_URL = os.getenv("REDIS_URL") or "redis://localhost:6379/0"
