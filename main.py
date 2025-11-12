import os
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Player as PlayerSchema, Squad as SquadSchema, SquadPlayer as SquadPlayerSchema

app = FastAPI(title="Football Squad Builder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Utils to handle ObjectId
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    doc = dict(doc)
    if doc.get("_id"):
        doc["id"] = str(doc.pop("_id"))
    return doc


@app.get("/")
def read_root():
    return {"message": "Football API running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response


# ---------------------- Players Endpoints ----------------------
@app.get("/api/players")
def list_players(
    q: Optional[str] = None,
    nation: Optional[str] = None,
    league: Optional[str] = None,
    club: Optional[str] = None,
    position: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200)
):
    """Search players with simple filters"""
    filt: Dict[str, Any] = {}
    if q:
        # Simple case-insensitive search across name/club
        filt["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"club": {"$regex": q, "$options": "i"}},
            {"nation": {"$regex": q, "$options": "i"}},
        ]
    if nation:
        filt["nation"] = nation
    if league:
        filt["league"] = league
    if club:
        filt["club"] = club
    if position:
        filt["position"] = position

    docs = db["player"].find(filt).limit(limit)
    return [serialize_doc(d) for d in docs]


@app.post("/api/players")
def add_player(player: PlayerSchema):
    new_id = create_document("player", player)
    doc = db.player.find_one({"_id": ObjectId(new_id)})
    return serialize_doc(doc)


@app.post("/api/seed/players")
def seed_players():
    """Seed a small sample of 25/26 players for demo purposes"""
    samples = [
        {
            "name": "Kylian Mbappé",
            "nation": "France",
            "league": "Ligue 1",
            "club": "Paris SG",
            "position": "ST",
            "rating": 92,
            "pace": 97, "shooting": 90, "passing": 84, "dribbling": 93, "defending": 36, "physical": 82,
            "img": "https://static.futdb.app/players/mbappe.png"
        },
        {
            "name": "Erling Haaland",
            "nation": "Norway",
            "league": "Premier League",
            "club": "Manchester City",
            "position": "ST",
            "rating": 92,
            "pace": 89, "shooting": 94, "passing": 65, "dribbling": 80, "defending": 45, "physical": 88,
            "img": "https://static.futdb.app/players/haaland.png"
        },
        {
            "name": "Kevin De Bruyne",
            "nation": "Belgium",
            "league": "Premier League",
            "club": "Manchester City",
            "position": "CM",
            "rating": 91,
            "pace": 74, "shooting": 86, "passing": 93, "dribbling": 88, "defending": 64, "physical": 78,
            "img": "https://static.futdb.app/players/debruyne.png"
        },
        {
            "name": "Jude Bellingham",
            "nation": "England",
            "league": "LaLiga",
            "club": "Real Madrid",
            "position": "CM",
            "rating": 89,
            "pace": 82, "shooting": 82, "passing": 85, "dribbling": 88, "defending": 78, "physical": 86,
            "img": "https://static.futdb.app/players/bellingham.png"
        },
        {
            "name": "Virgil van Dijk",
            "nation": "Netherlands",
            "league": "Premier League",
            "club": "Liverpool",
            "position": "CB",
            "rating": 90,
            "pace": 73, "shooting": 60, "passing": 71, "dribbling": 72, "defending": 91, "physical": 86,
            "img": "https://static.futdb.app/players/vandijk.png"
        },
        {
            "name": "Thibaut Courtois",
            "nation": "Belgium",
            "league": "LaLiga",
            "club": "Real Madrid",
            "position": "GK",
            "rating": 90,
            "pace": 0, "shooting": 0, "passing": 0, "dribbling": 0, "defending": 0, "physical": 0,
            "img": "https://static.futdb.app/players/courtois.png"
        },
    ]
    inserted = 0
    for p in samples:
        exists = db.player.find_one({"name": p["name"], "club": p["club"]})
        if not exists:
            create_document("player", PlayerSchema(**p))
            inserted += 1
    return {"inserted": inserted}


# ---------------------- Squad + Chemistry ----------------------

# A simple 4-3-3 slot map (0..10). We will compute chemistry as shared attributes among teammates.
SQUAD_SLOTS = list(range(11))


def compute_squad_stats(player_docs: List[Dict[str, Any]]):
    placed = [p for p in player_docs if p is not None]
    if not placed:
        return {"players": 0, "avg_rating": 0, "chemistry": 0}

    avg = round(sum(p.get("rating", 0) for p in placed) / len(placed), 1)

    # Very simple chemistry: for each player, count teammates sharing club(2), league(1), nation(1), max 3
    total_chem = 0
    for i, p in enumerate(placed):
        club_links = sum(1 for t in placed if t is not p and t.get("club") == p.get("club"))
        league_links = sum(1 for t in placed if t is not p and t.get("league") == p.get("league"))
        nation_links = sum(1 for t in placed if t is not p and t.get("nation") == p.get("nation"))
        score = 0
        if club_links >= 1:
            score += 2
        if league_links >= 2 or league_links >= 1:
            score += 1
        if nation_links >= 1:
            score += 1
        score = min(score, 3)
        total_chem += score

    # Cap team chemistry at 33 (11 players * 3)
    return {"players": len(placed), "avg_rating": avg, "chemistry": total_chem, "max_chemistry": 33}


class CalcBody(BaseModel):
    player_ids: List[Optional[str]]  # length up to 11 positions


@app.post("/api/calc")
def calc_stats(body: CalcBody):
    ids = [ObjectId(pid) for pid in body.player_ids if pid]
    docs_by_id = {str(d["_id"]): d for d in db.player.find({"_id": {"$in": ids}})}
    ordered_docs: List[Optional[Dict[str, Any]]] = []
    for pid in body.player_ids:
        if pid and pid in docs_by_id:
            ordered_docs.append(serialize_doc(docs_by_id[pid]))
        elif pid:
            try:
                d = db.player.find_one({"_id": ObjectId(pid)})
                ordered_docs.append(serialize_doc(d) if d else None)
            except Exception:
                ordered_docs.append(None)
        else:
            ordered_docs.append(None)
    stats = compute_squad_stats([d for d in ordered_docs if d])
    return {"players": ordered_docs, "stats": stats}


@app.get("/api/squads")
def get_squads():
    squads = db.squad.find({}).sort("_id", -1).limit(50)
    return [serialize_doc(s) for s in squads]


@app.post("/api/squads")
def create_squad(squad: SquadSchema):
    if squad.players and len(squad.players) > 11:
        raise HTTPException(status_code=400, detail="Max 11 players in starting XI")
    new_id = create_document("squad", squad)
    doc = db.squad.find_one({"_id": ObjectId(new_id)})
    return serialize_doc(doc)


class UpdateSquadBody(BaseModel):
    name: Optional[str] = None
    formation: Optional[str] = None
    players: Optional[List[SquadPlayerSchema]] = None


@app.put("/api/squads/{squad_id}")
def update_squad(squad_id: str, body: UpdateSquadBody):
    try:
        oid = ObjectId(squad_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid squad id")

    updates: Dict[str, Any] = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if "players" in updates and updates["players"] and len(updates["players"]) > 11:
        raise HTTPException(status_code=400, detail="Max 11 players")

    # Convert Pydantic models to dicts if present
    if "players" in updates and updates["players"]:
        updates["players"] = [p.model_dump() if hasattr(p, "model_dump") else dict(p) for p in updates["players"]]

    res = db.squad.update_one({"_id": oid}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Squad not found")
    doc = db.squad.find_one({"_id": oid})
    return serialize_doc(doc)


@app.get("/api/squads/{squad_id}/calc")
def calc_squad(squad_id: str):
    try:
        oid = ObjectId(squad_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid squad id")
    squad = db.squad.find_one({"_id": oid})
    if not squad:
        raise HTTPException(status_code=404, detail="Squad not found")
    players_map: Dict[int, Optional[str]] = {sp.get("slot"): sp.get("player_id") for sp in squad.get("players", [])}
    ids = [players_map.get(i) for i in SQUAD_SLOTS]
    calc = calc_stats(CalcBody(player_ids=ids))
    return calc


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
