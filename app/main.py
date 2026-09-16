from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import catalogue_qa, database, semantic_search


class CatalogueQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@asynccontextmanager
async def lifespan(app):
    database.initialize()
    yield


app = FastAPI(title="CampusSwap", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=database.ROOT / "app" / "static"), name="static")


def page(name, status_code=200):
    return FileResponse(database.ROOT / "app" / "pages" / name, status_code=status_code)


@app.get("/", include_in_schema=False)
def home():
    return page("index.html")


@app.get("/notes", include_in_schema=False)
def notes():
    return page("notes.html")


@app.get("/ask", include_in_schema=False)
def ask():
    return page("ask.html")


@app.get("/listings/{listing_id}", include_in_schema=False)
def detail(listing_id: int):
    return page("listing.html", 200 if database.get_listing(listing_id) else 404)


@app.get("/api/listings")
def listings(q: str = Query(default="", max_length=200), category: str = Query(default="", max_length=80)):
    return database.browse(q.strip(), category)


@app.get("/api/semantic-listings")
def semantic_listings(q: str = Query(min_length=1, max_length=200), category: str = Query(default="", max_length=80)):
    try:
        return semantic_search.search(q.strip(), category)
    except semantic_search.SemanticSearchUnavailable:
        raise HTTPException(status_code=503, detail="Semantic search is temporarily unavailable")


@app.post("/api/catalogue-qa")
def catalogue_question(payload: CatalogueQuestion):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be blank")
    try:
        return catalogue_qa.answer(question)
    except catalogue_qa.CatalogueQAUnavailable:
        raise HTTPException(status_code=503, detail="Catalogue Q&A is temporarily unavailable")


@app.get("/api/categories")
def categories():
    return database.categories()


@app.get("/api/listings/{listing_id}")
def listing(listing_id: int):
    item = database.get_listing(listing_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return item
