import cloudinary
from dotenv import load_dotenv
import os

# Load biến môi trường từ file .env
load_dotenv(encoding='utf-8')

def init_cloudinary():
    cloudinary.config(
        cloud_name="dxusasr4c",
        api_key="882845991834671",
        api_secret="TBeB6Fca3ozXAyQYTaLcN8DvKY8",
        secure=True
    )
