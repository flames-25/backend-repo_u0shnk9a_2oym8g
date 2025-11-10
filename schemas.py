"""
Database Schemas – Parfum App (FR)

Chaque classe = une collection MongoDB (nom en minuscule).

Collections principales:
- Brand
- NoteItem (ontologie normalisée)
- Perfume
- Review
- CommunityVotes
- UserProfile
- Embedding
- Affiliation
"""

from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field

# Référentiel d'ontologie des notes
class NoteItem(BaseModel):
    nom_normalise: str = Field(..., description="Nom standardisé: ex. 'vanille'")
    synonymes: List[str] = Field(default_factory=list)
    famille_ontologique: Literal[
        "agrumes","floral_blanc","floral","aromatique","epice",
        "resine","ambre_vanille","boise","gourmand","fruite",
        "marin_mineral","cuire_tabac","musque","vert"
    ]

# Marque
class Brand(BaseModel):
    nom: str
    pays: Optional[str] = None
    site: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

# Parfum
class Perfume(BaseModel):
    nom: str
    brand_id: str
    annee: Optional[int] = None
    createur: Optional[str] = None
    concentration: Optional[Literal["EDT","EDP","Parfum"]] = None
    familles: List[str] = Field(default_factory=list, description="ex: ['citrus','aromatique']")
    accords_principaux: List[str] = Field(default_factory=list)
    pyramide_notes: Dict[str, List[str]] = Field(..., description="cles: tete/coeur/fond")
    sillage: Optional[int] = Field(None, ge=1, le=3, description="1 discret, 2 présent, 3 signature")
    tenue: Optional[int] = Field(None, ge=1, le=3, description="1 courte, 2 journée, 3 soirée+")
    saison: List[str] = Field(default_factory=list)
    occasions: List[str] = Field(default_factory=list)
    prix_eur: Optional[float] = None
    medias: Dict[str, Optional[str]] = Field(default_factory=dict)
    description: Optional[str] = None
    popularite: Optional[float] = Field(None, ge=0, le=1)

# Avis rédactionnels (optionnel)
class Review(BaseModel):
    perfume_id: str
    user_id: Optional[str] = None
    rating: int = Field(..., ge=1, le=5)
    texte: Optional[str] = None
    pays: Optional[str] = None

class CommunityVotes(BaseModel):
    perfume_id: str
    sillage: Optional[int] = Field(None, ge=1, le=3)
    tenue: Optional[int] = Field(None, ge=1, le=3)
    notes_percues: List[str] = Field(default_factory=list)
    confiance: Optional[int] = Field(None, ge=1, le=100)

class UserProfile(BaseModel):
    langues: List[str] = Field(default_factory=lambda: ["fr"]) 
    familles_aimees: List[str] = Field(default_factory=list)
    familles_evitees: List[str] = Field(default_factory=list)
    notes_aimees: List[str] = Field(default_factory=list)
    notes_evitees: List[str] = Field(default_factory=list)
    sillage_cible: Optional[int] = None
    tenue_cible: Optional[int] = None
    contextes: List[str] = Field(default_factory=list)
    saisons: List[str] = Field(default_factory=list)
    budget_range: Optional[str] = None
    references_aimees: List[str] = Field(default_factory=list)

class Embedding(BaseModel):
    perfume_id: str
    vector: List[float]
    source: Optional[str] = None
    dim: int

class Affiliation(BaseModel):
    perfume_id: str
    marchands: List[str] = Field(default_factory=list)
    prix_localises: Dict[str, float] = Field(default_factory=dict)
    liens: List[str] = Field(default_factory=list)
    pays_dispos: List[str] = Field(default_factory=list)
