#Central configuration for the Flask app
#Loads environment variables and defines shared constants

import os

from dotenv import load_dotenv

# Load variables from .env into the environment

load_dotenv()

# Paths

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# Upload restrictions

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32 MB


# DeepSeek API credentials / endpoint

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "DeepSeek-V4.1-Flash")

# Image processing

MAX_IMAGE_DIM = 1600  # downscale images to this max dimension before sending


# Flask secret

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")