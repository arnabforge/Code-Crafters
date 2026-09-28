from typing import Optional
from pydantic import BaseModel, Field

class ProfileIn(BaseModel):
    owner_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=180)
    vehicle_id: str
    registration: Optional[str] = Field(default="", max_length=40)
    battery_pct: float = Field(ge=0, le=100)
    personal_range_km: Optional[float] = Field(default=None, ge=20, le=2000)

class PurchaseIn(BaseModel):
    owner_id: int
    plan: str = Field(min_length=2, max_length=40)
    amount: str = Field(min_length=1, max_length=80)

class PlanIn(BaseModel):
    owner_id: Optional[int] = None
    source: str = Field(min_length=2, max_length=300)
    destination: str = Field(min_length=2, max_length=300)
    vehicle_id: str
    battery_pct: float = Field(ge=0, le=100)
    personal_range_km: Optional[float] = Field(default=None, ge=20, le=2000)
    subscription: str = Field(default="free", pattern="^(free|premium)$")

class PlaceAutocompleteIn(BaseModel):
    input: str = Field(min_length=2, max_length=300)
