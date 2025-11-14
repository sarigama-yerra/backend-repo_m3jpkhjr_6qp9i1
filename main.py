import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Ctfuser, Challenge, Submission

app = FastAPI(title="CTF Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------
# Helpers
# ----------------------

def oid(obj):
    return ObjectId(str(obj))


def to_str_id(doc):
    if doc is None:
        return None
    d = dict(doc)
    if "_id" in d:
        d["_id"] = str(d["_id"])
    return d


# ----------------------
# Seed demo challenges
# ----------------------
@app.on_event("startup")
def seed_challenges():
    if db is None:
        return
    count = db["challenge"].count_documents({})
    if count == 0:
        demos = [
            Challenge(
                title="Warmup: Hello Flag",
                category="Misc",
                difficulty="Easy",
                points=50,
                description="Temukan flag tersembunyi di deskripsi ini. Format: CTF{hello_world}",
                flag="CTF{hello_world}",
            ).model_dump(),
            Challenge(
                title="Crypto: Caesar Shift",
                category="Crypto",
                difficulty="Easy",
                points=100,
                description="Pesan dienkripsi dengan pergeseran 3. Pecahkan untuk menemukan flag: CTF{...}",
                flag="CTF{caesar_3_shift}",
            ).model_dump(),
            Challenge(
                title="Web: Cookie Monster",
                category="Web",
                difficulty="Medium",
                points=200,
                description="Baca cookie dengan benar untuk mendapatkan flag.",
                flag="CTF{cookie_finder}",
            ).model_dump(),
        ]
        for d in demos:
            create_document("challenge", d)


# ----------------------
# Models for requests
# ----------------------
class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class SubmitFlagRequest(BaseModel):
    user_id: str
    challenge_id: str
    flag: str


# ----------------------
# Auth Endpoints (demo)
# ----------------------
@app.post("/auth/register")
def register(req: RegisterRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    existing = db["ctfuser"].find_one({"email": req.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = Ctfuser(username=req.username, email=req.email, password=req.password)
    uid = create_document("ctfuser", user)
    doc = db["ctfuser"].find_one({"_id": ObjectId(uid)})
    return {"user": to_str_id(doc)}


@app.post("/auth/login")
def login(req: LoginRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    user = db["ctfuser"].find_one({"email": req.email})
    if not user or user.get("password") != req.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"user": to_str_id(user)}


# ----------------------
# Challenge Endpoints
# ----------------------
@app.get("/challenges")
def list_challenges():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    items = db["challenge"].find({}, {"flag": 0})  # hide flags
    return {"challenges": [to_str_id(x) for x in items]}


@app.get("/challenges/{challenge_id}")
def get_challenge(challenge_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    item = db["challenge"].find_one({"_id": oid(challenge_id)}, {"flag": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return {"challenge": to_str_id(item)}


# ----------------------
# Submission & Scoring
# ----------------------
@app.post("/submit")
def submit_flag(req: SubmitFlagRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    user = db["ctfuser"].find_one({"_id": oid(req.user_id)})
    ch = db["challenge"].find_one({"_id": oid(req.challenge_id)})
    if not user or not ch:
        raise HTTPException(status_code=404, detail="User or Challenge not found")

    already = str(req.challenge_id) in [str(x) for x in user.get("solved", [])]
    correct = req.flag.strip() == ch.get("flag")

    sub = Submission(user_id=str(req.user_id), challenge_id=str(req.challenge_id), flag=req.flag, correct=correct)
    create_document("submission", sub)

    if correct and not already:
        # update user score and solved list
        db["ctfuser"].update_one(
            {"_id": oid(req.user_id)},
            {"$inc": {"score": ch.get("points", 0)}, "$addToSet": {"solved": str(req.challenge_id)}}
        )
        user = db["ctfuser"].find_one({"_id": oid(req.user_id)})
    return {"correct": correct, "user": to_str_id(user)}


# ----------------------
# Stats
# ----------------------
@app.get("/stats")
def stats(limit: int = 10):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    users = list(db["ctfuser"].find({}, {"password": 0}).sort("score", -1).limit(limit))
    # total solves per user
    for u in users:
        u["solves"] = len(u.get("solved", []))
    return {"leaderboard": [to_str_id(u) for u in users]}


@app.get("/")
def read_root():
    return {"message": "CTF Backend Running"}


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
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
