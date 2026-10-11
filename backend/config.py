import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'wastewise.db'}")
ML_MODEL_DIR = BASE_DIR / "backend" / "ml" / "artifacts"
ML_MODEL_DIR.mkdir(parents=True, exist_ok=True)

# AWS Settings (Optional)
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_BEDROCK_MODEL_ID = os.getenv("AWS_BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
USE_AWS_AI = bool(AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY)
