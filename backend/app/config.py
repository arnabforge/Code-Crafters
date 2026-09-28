from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE, override=False)

GOOGLE_MAPS_SERVER_KEY = os.getenv("GOOGLE_MAPS_SERVER_KEY", "").strip()
GOOGLE_MAPS_BROWSER_KEY = os.getenv("GOOGLE_MAPS_BROWSER_KEY", "").strip()
OPENCHARGEMAP_API_KEY = os.getenv("OPENCHARGEMAP_API_KEY", "").strip()
GOOGLE_REGION_CODE = os.getenv("GOOGLE_REGION_CODE", "").strip().upper()
CORS_ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
EV_ADMIN_TOKEN = os.getenv("EV_ADMIN_TOKEN", "").strip()
DB_PATH = Path(os.getenv("EV_DB_PATH", str(BASE_DIR / "evchargeroute.db")))
