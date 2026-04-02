import os
from dotenv import load_dotenv

load_dotenv()

SERVICE_KEY: str = os.environ["SERVICE_KEY"]
REDIS_URL: str = os.environ["REDIS_URL"]
ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]
DATABASE_URL: str = os.environ["DATABASE_URL"]
