from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()  # Gets our DATABASE_URL without leaking private data

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = create_client(url, key)