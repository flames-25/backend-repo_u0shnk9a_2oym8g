import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from database import db, create_document, get_documents

app = FastAPI(title="Parfum API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "API Parfums prête"}


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
            response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:100]}"
        else:
            response["database"] = "❌ Not Available"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:100]}"
    return response


# --- Modèles pour endpoints ---
class QuizInput(BaseModel):
    familles_aimees: List[str] = []
    familles_evitees: List[str] = []
    notes_aimees: List[str] = []
    notes_evitees: List[str] = []
    sillage_cible: Optional[int] = None
    tenue_cible: Optional[int] = None
    contextes: List[str] = []
    saisons: List[str] = []
    budget_range: Optional[str] = None
    references_aimees: List[str] = []


# --- Endpoints catalogue minimal (MVP) ---
@app.get("/api/perfumes")
def list_perfumes(
    q: Optional[str] = Query(None, description="Recherche par nom, marque, note"),
    famille: Optional[str] = None,
    note: Optional[str] = None,
    limit: int = 20
):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    filt: Dict[str, Any] = {}
    if q:
        filt["$or"] = [
            {"nom": {"$regex": q, "$options": "i"}},
            {"accords_principaux": {"$elemMatch": {"$regex": q, "$options": "i"}}},
            {"pyramide_notes.tete": {"$elemMatch": {"$regex": q, "$options": "i"}}},
            {"pyramide_notes.coeur": {"$elemMatch": {"$regex": q, "$options": "i"}}},
            {"pyramide_notes.fond": {"$elemMatch": {"$regex": q, "$options": "i"}}},
        ]
    if famille:
        filt["familles"] = famille
    if note:
        filt["$or"] = filt.get("$or", []) + [
            {"accords_principaux": note},
            {"pyramide_notes.tete": note},
            {"pyramide_notes.coeur": note},
            {"pyramide_notes.fond": note},
        ]

    docs = get_documents("perfume", filt, limit)
    # cast ObjectId to str
    for d in docs:
        d["_id"] = str(d.get("_id"))
    return {"items": docs}


@app.post("/api/quiz/recommendations")
def quiz_recommendations(payload: QuizInput):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    # Règles simples placeholder conformes à la spec de scoring
    filt: Dict[str, Any] = {}
    if payload.familles_evitees:
        filt["familles"] = {"$nin": payload.familles_evitees}
    if payload.notes_evitees:
        filt["pyramide_notes.tete"] = {"$nin": payload.notes_evitees}

    candidates = get_documents("perfume", filt, 200)

    def base_score(p: Dict[str, Any]) -> float:
        score = 0.0
        # familles aimées
        score += 2.0 * sum(1 for f in p.get("familles", []) if f in payload.familles_aimees)
        # notes aimées (tete/coeur/fond/accords)
        notes_all = set(p.get("accords_principaux", [])) | set(p.get("pyramide_notes", {}).get("tete", [])) | set(p.get("pyramide_notes", {}).get("coeur", [])) | set(p.get("pyramide_notes", {}).get("fond", []))
        score += 1.5 * sum(1 for n in notes_all if n in set(payload.notes_aimees))
        # anti-surprise
        if any(n in notes_all for n in payload.notes_evitees):
            return -1e9
        # sillage/tenue
        if payload.sillage_cible and p.get("sillage"):
            score += 2 if payload.sillage_cible == p.get("sillage") else 1 if abs(payload.sillage_cible - p.get("sillage")) == 1 else 0
        if payload.tenue_cible and p.get("tenue"):
            score += 2 if payload.tenue_cible == p.get("tenue") else 1 if abs(payload.tenue_cible - p.get("tenue")) == 1 else 0
        # saison
        if payload.saisons:
            score += 1.0 if any(s in p.get("saison", []) for s in payload.saisons) else 0
        return score

    scored = [
        {"perfume": {**p, "_id": str(p.get("_id"))}, "score": base_score(p)}
        for p in candidates
    ]

    scored = [s for s in scored if s["score"] > -1e8]
    scored.sort(key=lambda x: x["score"], reverse=True)

    # Diversité: garantir >= 3 familles distinctes dans top10
    top = []
    familles_seen = set()
    for item in scored:
        fams = item["perfume"].get("familles", [])
        if len(top) < 10:
            if len(familles_seen) < 3:
                if any(f not in familles_seen for f in fams):
                    top.append(item)
                    familles_seen.update(fams)
            else:
                top.append(item)
    # Si insuffisant, compléter
    i = 0
    while len(top) < 10 and i < len(scored):
        if scored[i] not in top:
            top.append(scored[i])
        i += 1

    # Catégorisation
    top_sorted = top[:]
    top_sorted.sort(key=lambda x: x["score"], reverse=True)
    top_matchs = top_sorted[:3]
    budget_alt = [t for t in top_sorted if t["perfume"].get("prix_eur", 0) <= 120][:4]
    wildcards = []
    for t in top_sorted:
        fams = set(t["perfume"].get("familles", []))
        if not any(fams & set(x["perfume"].get("familles", [])) for x in top_matchs):
            wildcards.append(t)
        if len(wildcards) == 3:
            break

    def explain(p: Dict[str, Any]) -> str:
        why = []
        if payload.notes_aimees and any(n in p.get("accords_principaux", []) for n in payload.notes_aimees):
            why.append("accords alignés")
        if payload.sillage_cible and p.get("sillage") == payload.sillage_cible:
            why.append("sillage conforme")
        if payload.tenue_cible and p.get("tenue") == payload.tenue_cible:
            why.append("tenue conforme")
        if payload.saisons and any(s in p.get("saison", []) for s in payload.saisons):
            why.append("adapté à la saison")
        base = ", ".join(why[:2]) or "proche de tes goûts"
        return f"Tu as aimé {', '.join(payload.notes_aimees[:2])}. Ici: {base}."

    def serialize(items: List[Dict[str, Any]]):
        out = []
        for it in items:
            p = it["perfume"]
            out.append({
                "id": p.get("_id"),
                "nom": p.get("nom"),
                "marque": p.get("brand_id"),
                "prix_eur": p.get("prix_eur"),
                "familles": p.get("familles", []),
                "accords_principaux": p.get("accords_principaux", []),
                "sillage": p.get("sillage"),
                "tenue": p.get("tenue"),
                "saison": p.get("saison", []),
                "score": round(float(it["score"]), 3),
                "pourquoi": explain(p),
                "image": (p.get("medias") or {}).get("image"),
            })
        return out

    return {
        "top_matchs": serialize(top_matchs),
        "alternatives_budget": serialize(budget_alt),
        "wildcards": serialize(wildcards)
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
