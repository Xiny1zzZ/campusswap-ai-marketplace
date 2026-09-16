"""Small, server-side semantic retrieval service for the seeded catalogue."""
import json
import math
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app import database

GATEWAY_URL = "https://174.138.16.223/openrouter/v1/embeddings"
EMBEDDING_MODEL = "openai/text-embedding-3-small"
MINIMUM_SIMILARITY = 0.30
MAX_RESULTS = 5


class SemanticSearchUnavailable(Exception):
    """Raised when configuration or the embedding gateway is unavailable."""


def listing_text(item):
    return "\n".join((item["title"], item["description"], item["category"], item["condition"]))


def request_embeddings(inputs):
    """Call the OpenAI-compatible embeddings endpoint without exposing the key."""
    api_key = os.environ.get("CLASSGW_KEY")
    if not api_key:
        raise SemanticSearchUnavailable("Semantic search is not configured.")

    payload = json.dumps({"model": EMBEDDING_MODEL, "input": inputs}).encode("utf-8")
    request = Request(GATEWAY_URL, data=payload, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }, method="POST")
    try:
        with urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
        return [entry["embedding"] for entry in sorted(body["data"], key=lambda entry: entry["index"])]
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError, TypeError):
        raise SemanticSearchUnavailable("Semantic search is temporarily unavailable.") from None


def cosine_similarity(left, right):
    if len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    magnitude = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return numerator / magnitude if magnitude else 0.0


def search(query, category=""):
    """Embed a query, compare it with cached listing vectors, and return listings only."""
    ranked = rank_catalogue(query, category)
    return [item for score, item in ranked if score >= MINIMUM_SIMILARITY][:MAX_RESULTS]


def rank_catalogue(query, category=""):
    """Return every selected catalogue listing with its cosine score, highest first."""
    if not os.environ.get("CLASSGW_KEY"):
        raise SemanticSearchUnavailable("Semantic search is not configured.")

    items = database.browse(category=category)
    missing = []
    vectors = {}
    for item in items:
        text = listing_text(item)
        vector = database.get_embedding(item["id"], EMBEDDING_MODEL, text)
        if vector is None:
            missing.append((item, text))
        else:
            vectors[item["id"]] = vector

    if missing:
        for (item, text), vector in zip(missing, request_embeddings([text for _, text in missing])):
            database.save_embedding(item["id"], EMBEDDING_MODEL, text, vector)
            vectors[item["id"]] = vector

    query_vector = request_embeddings([query])[0]
    return sorted(
        ((cosine_similarity(query_vector, vectors[item["id"]]), item) for item in items),
        key=lambda result: (-result[0], result[1]["id"]),
    )
