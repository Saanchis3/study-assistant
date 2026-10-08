import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "openai/gpt-oss-20b")
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "4"))