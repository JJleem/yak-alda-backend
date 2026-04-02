import os
from dotenv import load_dotenv

load_dotenv()

SERVICE_KEY: str = os.environ["SERVICE_KEY"]
REDIS_URL: str = os.environ["REDIS_URL"]
ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]
