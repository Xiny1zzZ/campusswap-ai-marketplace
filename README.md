# CampusSwap

A student second-hand marketplace demo for the CognitioLabs Associate Forward Deployed Engineer assessment. This MVP supports browsing 36 fictional seeded listings, item details, one unified semantic search box with category filtering, and the separate Ask CampusSwap catalogue Q&A page.

## Run locally

Use Python 3.10 or newer. From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 to browse, http://127.0.0.1:8000/notes for project notes, or http://127.0.0.1:8000/docs for the API reference. Stop with Ctrl+C. Browsing an empty search needs no API key; a non-empty unified search needs the server-side key described below.

On macOS/Linux, create the environment with `python3 -m venv .venv` and use `.venv/bin/python` for subsequent commands.

To enable natural-language search, set the gateway key in the server environment before starting Uvicorn. Do not put this key in a client-side file or commit it:

```powershell
$env:CLASSGW_KEY = "your-gateway-key"
```

Without this variable, empty catalogue browsing still works and non-empty unified searches or Ask CampusSwap requests return safe `503` responses.

## How it works

- FastAPI serves pages, static assets, and read-only JSON endpoints from one application.
- Python's built-in SQLite library stores listings using parameterized queries.
- Startup reconciles the seed-owned fictional catalogue in `data/seed_listings.json` into `data/campusswap.db`, which Git ignores. This means an existing local database receives new or revised seed listings on restart; restarts do not duplicate items. The demo has no listing-management feature, so there is no user-created catalogue data to preserve.
- Vue 3 is loaded directly from the unpkg CDN as a native browser ES module; no Vite, npm, or frontend build step is used. `app/static/js/app.js` imports Vue and calls `createApp()` for the `#browse-app` and `#detail-app` roots. Vue renders the fetched data with escaped template interpolation. Browse filters are preserved in the URL and respond to browser back/forward navigation.
- The browse UI provides one unified search box: users can enter an item name or describe what they need. Any non-empty browse query calls `/api/semantic-listings`, which uses `openai/text-embedding-3-small`, cosine similarity against existing SQLite listings, the `0.30` threshold, and the five-result cap. An empty query calls `/api/listings` to show the normal catalogue without an embedding request. The literal, case-insensitive `/api/listings?q=...` keyword API remains available, but users no longer choose a search mode. The `0.30` minimum is an empirically chosen starting point from testing this 36-item seeded catalogue, not a universal relevance threshold.
- Browse listing links preserve the current whitelisted `q` and `category` parameters. Listing details show Back to results for filtered browse links and safely reconstruct only the local browse URL; unfiltered links show Back to browse.
- The Python backend calls `https://174.138.16.223/openrouter/v1/embeddings` with `openai/text-embedding-3-small`. It reads `CLASSGW_KEY` only on the server and caches listing vectors in SQLite's `listing_embeddings` table. Startup keeps vectors for unchanged indexed text and removes only stale vectors; new listings are embedded lazily on the first applicable natural-language search. No vector database is used.
- Ask CampusSwap is a separate `/ask` page backed by `POST /api/catalogue-qa`. It uses the same cached `openai/text-embedding-3-small` retrieval to relevance-order the catalogue, then sends all 36 compact, explicit SQLite records plus the question to `gpt-5.6-terra` through the CognitioLabs OpenAI-compatible gateway. Full-catalogue context is intentional for this small demo: price and location facts could be missed by semantic Top-K retrieval. The model returns concise answer text and candidate listing IDs; the server validates every ID against SQLite before returning real listing records for clickable cards. Cards default to at most eight; an explicit request for all matching items can return all validated matches. The model is instructed to use only supplied records and to say when the seeded catalogue lacks a requested fact.
- Ask listing cards use `/listings/{id}?from=ask`. The browser saves only the visible Ask conversation in sessionStorage—questions, answers, validated listing-card fields, and `has_more`—so Back to Ask CampusSwap restores that session. It does not store keys, prompts, vectors, scores, errors, or gateway details.
- Prices use integer cents and display in SGD. Search matches a literal, case-insensitive substring of titles or descriptions; category matching is exact.
- Update `app/pages/notes.html` in the same task as important feature changes, following `AGENTS.md`.

The catalogue is entirely seeded demo data: every seller, price, condition, and Singapore pickup location is fictional. Restart the server after changing the seed file to reconcile the local demo database. Removing `data/campusswap.db` is optional and simply creates a fresh local cache on the next startup.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use a temporary SQLite database and mock all embedding and chat-completion calls, keeping catalogue and cache assertions deterministic and making zero real gateway calls. They cover seed reconciliation, keyword/category filtering, literal inputs, validation, missing listings, pages, assets, categories, semantic filtering, caching, grounded Q&A context construction, comparisons, missing facts, SQLite validation of Q&A card IDs, default card limits, explicit all-results requests, and safe error responses.

## Current limits

All sellers, listings, and locations are fictional examples; emoji are image placeholders. Accounts, authentication, payments, messaging, listing management, persistent chat history, and streaming chat are not implemented. Ask CampusSwap answers only from the supplied seeded-catalogue context; its grounding instructions reduce unsupported answers but have not been evaluated against adversarial prompts. Non-empty unified search and Ask CampusSwap need a valid `CLASSGW_KEY`, gateway access, and seeded SQLite listings; gateway errors are reported generically. Browse and detail pages require JavaScript and a network connection that can reach the Vue CDN. There is no pagination, sorting, or deployment setup. SQLite needs a writable local disk. Live browser and assistive-technology review remain unfinished. See the public /notes page for the full current state.
