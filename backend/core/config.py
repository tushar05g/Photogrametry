import os
from dotenv import load_dotenv

load_dotenv()  # This reads your .env file and loads all the KEY=VALUE pairs into the environment

DATABASE_URL = os.getenv("DATABASE_URL")

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
