# agent settings, every value here is recorded with each answer so runs can be compared
# model and temperature can be overridden in .env without touching code

import os

from dotenv import load_dotenv

from ingest import config as ingest_config

load_dotenv(ingest_config.ROOT / ".env")

MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")
# None -> parameter not sent, model default is used (some reasoning models only accept the default)
TEMPERATURE = float(os.environ["OPENAI_TEMPERATURE"]) if os.getenv("OPENAI_TEMPERATURE") else None

MAX_ATTEMPTS = 3        
MAX_ROWS_TO_MODEL = 50  # rows of a query result shown back to the model

DB_PATH = ingest_config.DB_PATH
