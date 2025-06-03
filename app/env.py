import os
from typing import cast
from dotenv import load_dotenv
load_dotenv()

SERVER_URL = cast(str, os.getenv("SERVER_URL"))
SERVER_API_KEY = cast(str, os.getenv("SERVER_API_KEY"))


if not SERVER_URL:
    raise ValueError("SERVER_URL environment variable is not set")
if not SERVER_API_KEY:
    raise ValueError("SERVER_API_KEY environment variable is not set")

