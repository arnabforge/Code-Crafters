# EVChargeRoute final setup

This build preserves the original website/UI and all existing features. Only the two charging-station features were changed:

1. Route Planner -> Charging candidates now discovers EV charging stations along the actual Google route using Places API (New) Search Along Route, with Open Charge Map used to enrich operator/status/ports/pricing and as a fallback.
2. Stations -> nearby station search uses Open Charge Map as the primary source and Google Places as a fallback when OCM returns no records.

## Backend `.env`

```env
GOOGLE_MAPS_SERVER_KEY=YOUR_GOOGLE_SERVER_KEY
OPENCHARGEMAP_API_KEY=YOUR_OPENCHARGEMAP_KEY
GOOGLE_REGION_CODE=IN
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
EV_ADMIN_TOKEN=YOUR_ADMIN_TOKEN
```

## Frontend `.env`

```env
VITE_API_BASE=http://localhost:8000
VITE_GOOGLE_MAPS_BROWSER_KEY=YOUR_GOOGLE_BROWSER_KEY
```

## Google Cloud APIs

Enable the APIs used by the existing project plus the new route-aware charging discovery:
- Maps JavaScript API (browser key)
- Geocoding API (server key)
- Routes API (server key)
- Places API (New) (server key)

## Run

Backend:

```powershell
cd backend
python -m venv venv
.\\venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend (second terminal):

```powershell
cd frontend
npm install
npm run dev
```
