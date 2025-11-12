"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict

# Core football schemas used by the app

Position = Literal[
    "GK","LB","CB","RB","LWB","RWB",
    "CDM","CM","CAM","LM","RM",
    "LW","RW","ST","CF"
]

class Player(BaseModel):
    """
    Football player document (FUT-style attributes)
    Collection name: "player"
    """
    name: str = Field(..., description="Player full name")
    nation: str = Field(..., description="Nationality")
    league: str = Field(..., description="Domestic league")
    club: str = Field(..., description="Club team")
    position: Position = Field(..., description="Primary position")
    rating: int = Field(..., ge=40, le=99, description="Overall rating")
    pace: int = Field(60, ge=1, le=99)
    shooting: int = Field(60, ge=1, le=99)
    passing: int = Field(60, ge=1, le=99)
    dribbling: int = Field(60, ge=1, le=99)
    defending: int = Field(60, ge=1, le=99)
    physical: int = Field(60, ge=1, le=99)
    img: Optional[str] = Field(None, description="Image URL for card art")

class SquadPlayer(BaseModel):
    slot: int = Field(..., ge=0, le=10, description="Index in starting XI grid 0..10")
    player_id: str = Field(..., description="Reference to player _id")

class Squad(BaseModel):
    """
    User-created squad with 11 players
    Collection name: "squad"
    """
    name: str = Field(..., description="Squad name")
    formation: str = Field("4-3-3", description="Formation label")
    players: List[SquadPlayer] = Field(default_factory=list, description="Starting XI mapping")
    meta: Dict[str, str] = Field(default_factory=dict)

# Example legacy schemas retained for reference
class User(BaseModel):
    name: str
    email: str
    address: str
    age: Optional[int] = None
    is_active: bool = True

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True
