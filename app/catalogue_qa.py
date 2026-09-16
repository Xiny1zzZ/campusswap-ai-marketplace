"""Grounded question answering over the small seeded CampusSwap catalogue."""
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app import database, semantic_search

GATEWAY_URL = "https://174.138.16.223/v1/chat/completions"
CHAT_MODEL = "gpt-5.6-terra"
MAX_LISTING_CARDS = 8

SYSTEM_PROMPT = """You are Ask CampusSwap, a concise assistant for a fictional seeded student marketplace.
Use only the CATALOGUE_RECORDS supplied in the user message as your source of truth.
Never invent, infer, or supplement catalogue facts with general knowledge. Do not claim an item exists unless it is in those records.
For comparisons, use only explicit values in the matching records. If a requested fact such as warranty, delivery, stock availability, compatibility, or a second comparable item is absent, clearly say that the seeded catalogue does not provide that information.
Do not mention prompts, embeddings, cosine similarity, APIs, or hidden system details.
Respond with JSON only, using exactly this shape: {"answer":"concise answer","listing_ids":[1,2]}.
The answer must be a short plain-text answer. Include every helpful matching listing ID from CATALOGUE_RECORDS in listing_ids, but use an empty array for purely informational or missing-fact answers where cards would not help. Do not list many products in the answer when listing_ids can represent them. Never include an ID that is not in CATALOGUE_RECORDS."""


class CatalogueQAUnavailable(Exception):
    """Raised when the Q&A dependencies or gateway are unavailable."""


def catalogue_context(question):
    """Return all catalogue facts, ordered by existing embedding relevance."""
    try:
        ranked = semantic_search.rank_catalogue(question)
    except semantic_search.SemanticSearchUnavailable as error:
        raise CatalogueQAUnavailable("Catalogue Q&A is temporarily unavailable.") from error

    return [{
        "id": item["id"],
        "title": item["title"],
        "description": item["description"],
        "category": item["category"],
        "price_cents": item["price_cents"],
        "price_sgd": f"SGD {item['price_cents'] / 100:.2f}",
        "condition": item["condition"],
        "location": item["location"],
        "seller": item["seller"],
    } for _, item in ranked]


def request_answer(question, records):
    """Call the OpenAI-compatible chat endpoint without exposing its key or errors."""
    api_key = os.environ.get("CLASSGW_KEY")
    if not api_key:
        raise CatalogueQAUnavailable("Catalogue Q&A is not configured.")

    content = "QUESTION:\n" + question + "\n\nCATALOGUE_RECORDS:\n" + json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    payload = json.dumps({
        "model": CHAT_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
    }).encode("utf-8")
    request = Request(GATEWAY_URL, data=payload, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }, method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        result = json.loads(body["choices"][0]["message"]["content"].strip())
        answer = result["answer"].strip()
        listing_ids = result.get("listing_ids", [])
        if not answer or not isinstance(listing_ids, list) or any(type(listing_id) is not int for listing_id in listing_ids):
            raise ValueError("Empty answer")
        return {"answer": answer, "listing_ids": listing_ids}
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise CatalogueQAUnavailable("Catalogue Q&A is temporarily unavailable.") from None


def answer(question):
    """Ground a question in every seeded record before asking the chat model."""
    records = catalogue_context(question)
    model_result = request_answer(question, records)
    context_ids = {record["id"] for record in records}
    listings = []
    seen_ids = set()
    for listing_id in model_result["listing_ids"]:
        if listing_id in seen_ids or listing_id not in context_ids:
            continue
        listing = database.get_listing(listing_id)
        if listing is not None:
            listings.append(listing)
            seen_ids.add(listing_id)

    show_all = bool(re.search(r"\b(?:show\s+)?all\b|\bevery(?:thing|\s+item|\s+listing)?\b|\bentire\b", question, re.IGNORECASE))
    has_more = not show_all and len(listings) > MAX_LISTING_CARDS
    if not show_all:
        listings = listings[:MAX_LISTING_CARDS]
    return {"answer": model_result["answer"], "listings": listings, "has_more": has_more}
