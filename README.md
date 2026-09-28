# EVChargeRoute 4.0 — Real Maps UX + Real Routes + Charger Intelligence

This version is rebuilt so that **places, owners, addresses and coordinates are not hard-coded into the UI**.

The architecture is:

- **React + Vite + React-Bootstrap** — responsive application UI.
- **Google Maps JavaScript API** — interactive map rendering.
- **Google Places API (New)** — live place/address autocomplete and place details through the FastAPI server.
- **Google Geocoding API** — final address/coordinate resolution for routing.
- **Google Routes API** — actual road distance, duration and route geometry.
- **Google Routes Matrix API** — efficient source→charger and charger→destination road-leg calculations.
- **Open Charge Map API** — charger locations, operators, connector information, reported status and reported usage/pricing when present.
- **SQLite** — owner profiles, simulated purchases and route history.
- **Vehicle catalog JSON** — editable reference vehicle data, kept outside React components and Python logic.
- **Queue simulator** — clearly separated from provider data because a universal live queue feed is not available from OCM.

## 1. What was removed

The earlier prototype contained fixed examples such as:

- a default city for source/destination;
- fixed latitude/longitude for the Stations page;
- a pre-filled owner profile;
- hard-coded owner/team information in the UI;
- a browser fallback that could make route distance appear plausible without a real route.

Those are removed.

The user now starts with an empty owner profile and empty route inputs.

The only static reference data is the **vehicle catalog** in:

`backend/app/vehicles.json`

That is intentionally a data file rather than hard-coded UI logic, so the catalog can be edited or replaced without rewriting the planner.

## 2. Google Maps Platform setup

Create one Google Cloud project for EVChargeRoute.

Enable:

1. Maps JavaScript API
2. Places API (New)
3. Geocoding API
4. Routes API

Google Maps Platform requires an appropriate billing setup for the APIs used by the project. Review the current Google pricing/quotas before public deployment.

### Browser key

Create a key for the React map:

`GOOGLE_MAPS_BROWSER_KEY`

In this project it is placed in:

`frontend/.env`

under the Vite name:

`VITE_GOOGLE_MAPS_BROWSER_KEY=`

Restrict it by HTTP referrer and allow only your development/deployed domains. Restrict the key to Maps JavaScript API (and only other browser APIs you intentionally use).

Example local referrers:

- `http://localhost:5173/*`
- `http://127.0.0.1:5173/*`

### Server key

Create a separate key for FastAPI:

`GOOGLE_MAPS_SERVER_KEY`

Put it only in:

`backend/.env`

Restrict it to the server-side APIs used by this project:

- Places API (New)
- Geocoding API
- Routes API

Do not put this key in React or a `VITE_` variable.

## 3. Open Charge Map setup

Create an Open Charge Map account/application and obtain an API key.

Put it only in:

`backend/.env`

as:

`OPENCHARGEMAP_API_KEY=`

The React browser never receives the OCM key.

OCM records can contain station/operator/connector/status/usage/pricing information, but provider-reported station status must not be interpreted as guaranteed live connector occupancy.

The queue count in this project is therefore explicitly a **simulation**.

## 4. Environment files

Both empty environment files are included:

```text
backend/.env
frontend/.env
```

They are intentionally empty so you can paste your own credentials.

Example files are also included:

```text
backend/.env.example
frontend/.env.example
```

### backend/.env

```env
GOOGLE_MAPS_SERVER_KEY=
OPENCHARGEMAP_API_KEY=
GOOGLE_REGION_CODE=
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
EV_ADMIN_TOKEN=
EV_DB_PATH=
```

`GOOGLE_REGION_CODE` is optional. For example, you can set `IN` if you want Places autocomplete biased toward India. Leaving it empty keeps the search globally oriented.

### frontend/.env

```env
VITE_API_BASE=http://localhost:8000
VITE_GOOGLE_MAPS_BROWSER_KEY=
VITE_TEAM_NAME=
VITE_TEAM_MEMBERS=
```

The team variables are optional. This prevents personal/team names from being hard-coded in the source.

## 5. Dotenv loading order

FastAPI loads environment variables before importing service code:

```text
app.main
  ↓
app.config
  ↓
load_dotenv(backend/.env)
  ↓
Google/OCM configuration constants
  ↓
services.py
```

This prevents the common problem where `services.py` reads environment variables before `.env` has been loaded.

The loader is in:

`backend/app/config.py`

and uses `python-dotenv`.

## 6. Run locally

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Check:

`http://localhost:8000/api/health`

The response shows whether Google server routing, Google browser configuration is no longer server-managed, and OCM are configured.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open:

`http://localhost:5173`

## 7. Google-style place search

The Route Planner no longer asks the user to type a raw address and hope that a geocoder understands it.

The UI behaves like a map-search field:

```text
User types:
    "air"

       ↓ debounce

FastAPI
       ↓
Google Places API (New)
       ↓
Suggestions

┌─────────────────────────────┐
│ Airport                     │
│ Airport Road                │
│ Airport Metro Station       │
│ ...                         │
└─────────────────────────────┘

       ↓ user selects

Place ID → Google Place Details
       ↓
coordinates + formatted address
       ↓
route planner
```

The backend endpoints are:

```text
GET /api/places/autocomplete?input=...
GET /api/places/{place_id}
```

This is also used by the Charging Stations page, so it no longer starts with a fixed city coordinate.

## 8. Real route calculation

The planner performs:

```text
Source text
   ↓
Google Places / Geocoding
   ↓
source coordinates

Destination text
   ↓
Google Places / Geocoding
   ↓
destination coordinates

source + destination
   ↓
Google Routes API
   ↓
real road distance
real travel duration
encoded route geometry
```

Therefore the planner does not use straight-line distance as the main journey distance.

## 9. Real charger discovery

The route geometry is sampled at several points.

For each sample:

```text
route point
   ↓
Open Charge Map nearby search
   ↓
charger records
```

Duplicate station records are removed.

A normalized station contains fields such as:

- station name
- latitude/longitude
- address
- operator
- reported status
- usage information
- reported usage cost when present
- connector type
- connector power
- connector quantity
- maximum reported power
- Open Charge Map record URL

## 10. Queue simulation

The charger API is not treated as a universal live occupancy source.

The application therefore adds:

```text
provider charger data
        +
5-minute time-bucketed deterministic simulation
        ↓
simulated vehicles waiting
```

This means the same station can show a changing queue during a demonstration without pretending that the number is live provider data.

The UI labels the values as:

**Queue simulation**

and

**Simulated wait**.

## 11. Vehicle model

Vehicle data is stored in:

`backend/app/vehicles.json`

Each vehicle can contain:

- battery capacity
- reference full-charge range
- charging port family
- maximum DC charging power
- AC charging power
- reference 10–80% time
- safety reserve
- source URL
- source note

To add another EV, add another JSON object rather than editing the React planner.

Example structure:

```json
{
  "example-ev": {
    "name": "Example EV",
    "manufacturer": "Example",
    "battery_kwh": 60,
    "reference_range_km": 450,
    "charging_port": "CCS2",
    "dc_kw": 100,
    "ac_kw": 11,
    "charge_10_80_min": 30,
    "reserve_pct": 10,
    "source_url": "...",
    "source_note": "..."
  }
}
```

## 12. Personalized range calculation

The owner can provide an observed full-charge range.

The model combines the reference vehicle value with the owner's observation:

```text
personalized range
    = 60% × reference range
    + 40% × owner observed range
```

If the owner does not provide an observation:

```text
personalized range = reference range
```

Then the safe usable range is:

```text
safe range
 = (battery SOC − safety reserve)
   / 100
   × personalized range
```

This is a planning estimate, not a guarantee of real-world range.

Real range can change with:

- speed
- traffic
- temperature
- HVAC use
- terrain
- driving style
- road surface
- tyre pressure
- battery condition
- vehicle load

## 13. Charging candidate algorithm

For every charger candidate, the model calculates:

```text
Source → charger
charger → destination
```

using Google's actual road network.

The candidate is reachable only if:

```text
source → charger distance <= current safe range
```

The model estimates:

- SOC on arrival at charger
- SOC needed to reach destination
- charging energy
- charging time
- simulated queue
- simulated waiting time
- route detour
- extra journey time

The effective candidate cost is approximately:

```text
candidate cost
 = source→charger drive time
 + queue wait
 + charging time
 + charger→destination drive time
```

The direct route is evaluated separately.

### Why no Dijkstra/A* over roads?

Google Routes already performs road-network routing. Rebuilding the entire global road graph inside this project would be unnecessary.

Instead, the project uses a smaller candidate graph:

```text
             Charger A
            /         \
Source ----             ---- Destination
            \         /
             Charger B
```

Each edge has real Google road distance/duration.

The charger node contributes queue and charging cost.

For multiple charging stops in a future version, the planner can be extended into an SOC-aware Dijkstra/A* or dynamic-programming state graph.

## 14. Database

SQLite is used for the prototype:

`backend/evchargeroute.db`

Tables:

### owners

Stores the owner profile and vehicle information.

### purchases

Stores simulated subscription purchases.

### route_history

Stores previous route-planning records.

No owner record is created until the user explicitly saves the profile.

## 15. Loading a saved owner

The Dashboard contains:

**Load saved profile**

Enter the same email used when saving.

FastAPI retrieves the matching database record and restores:

- owner name
- email
- vehicle
- registration
- battery SOC
- personal range estimate

There is no hard-coded owner account.

## 16. Inspecting and deleting database data

Open:

**Data Console**

Enter the backend `EV_ADMIN_TOKEN`.

The console can display:

- owners
- purchases
- route history

It can delete:

- one owner
- one purchase
- all prototype records

Deleting an owner cascades to that owner's purchase records.

You can also open the SQLite database using a SQLite GUI and run:

```sql
SELECT * FROM owners;
SELECT * FROM purchases;
SELECT * FROM route_history;
```

## 17. Security rules

Never commit real credentials.

The repository ignores:

```text
backend/.env
frontend/.env
*.db
```

The browser key is intentionally public but must be restricted by HTTP referrer and API.

The server Google key and OCM key stay server-side.

The Data Console is protected by `EV_ADMIN_TOKEN`.

For a public deployment, do not expose the Data Console to ordinary users without adding proper authentication/authorization.

## 18. Production deployment

For Netlify/Vercel frontend:

```text
VITE_API_BASE=https://your-backend.example
VITE_GOOGLE_MAPS_BROWSER_KEY=...
VITE_TEAM_NAME=...
VITE_TEAM_MEMBERS=...
```

For Render backend:

```text
GOOGLE_MAPS_SERVER_KEY=...
OPENCHARGEMAP_API_KEY=...
CORS_ORIGINS=https://your-frontend.example
EV_ADMIN_TOKEN=...
```

Do not copy local `.env` files into GitHub.

### Database warning

SQLite is appropriate for local/academic demonstration.

For a persistent hosted service, use PostgreSQL or another managed database. Hosted filesystems can be ephemeral, so a local SQLite file may not survive every deployment/restart configuration.

## 19. Current API responsibilities

```text
React
 │
 ├── Google Maps JS API
 │       └── map rendering
 │
 └── FastAPI
       │
       ├── Google Places API
       │       └── autocomplete/details
       │
       ├── Google Geocoding API
       │       └── coordinate resolution
       │
       ├── Google Routes API
       │       └── real route distance/time/polyline
       │
       ├── Google Routes Matrix API
       │       └── charger road-leg comparisons
       │
       ├── Open Charge Map API
       │       └── charger metadata
       │
       └── SQLite
               ├── owners
               ├── purchases
               └── route_history
```

This separation keeps secrets server-side, makes the map UX familiar, and prevents fixed places or fixed owner records from determining the model.
