# CampusSwap

CampusSwap is an AI-enabled second-hand marketplace demo for students, built for the CognitioLabs Associate Forward Deployed Engineer assessment.

The MVP includes 36 fictional seeded listings, responsive browsing and item-detail pages, category filtering, natural-language semantic search, and a dedicated Ask AI catalogue Q&A experience.

Users can search by item name or simply describe what they need. Ask AI can answer questions and compare items using the seeded catalogue, then return validated clickable listing cards.

The project is deployed as a public assessment demo and is designed to work on both desktop and mobile.

---

## Run locally

Use Python 3.10 or newer.

From the repository root in PowerShell:

```powershell
python -m venv .venv

.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open:

- `http://127.0.0.1:8000` — Browse the marketplace
- `http://127.0.0.1:8000/ask` — Ask AI
- `http://127.0.0.1:8000/notes` — Project notes
- `http://127.0.0.1:8000/docs` — API reference

Stop the local server with `Ctrl+C`.

Browsing the normal catalogue with an empty search does not require an API key. A non-empty semantic search or Ask AI request requires the server-side gateway key described below.

On macOS/Linux, create the environment with:

```bash
python3 -m venv .venv
```

Then use `.venv/bin/python` for subsequent commands.

---

## AI gateway configuration

To enable natural-language search and Ask AI, set the CognitioLabs gateway key in the server environment before starting Uvicorn.

Do not put this key in a client-side file or commit it to Git.

In PowerShell:

```powershell
$env:CLASSGW_KEY = "your-gateway-key"
```

Without this variable, the normal catalogue can still be browsed, but non-empty semantic searches and Ask AI requests return safe error responses.

The key is read only by the Python backend through the `CLASSGW_KEY` environment variable and is not exposed to the browser.

---

## How it works

### Application structure

- FastAPI serves the pages, static assets, and JSON endpoints from one application.
- Python's built-in SQLite library stores the seeded marketplace listings using parameterized queries.
- Vue 3 provides the interactive browse, listing, and Ask AI interfaces.
- The CognitioLabs gateway provides the embedding and language-model access used by the AI features.

The application intentionally keeps the architecture small for the assessment rather than introducing unnecessary infrastructure.

---

### Seeded catalogue

The fictional catalogue is stored in:

```text
data/seed_listings.json
```

Startup reconciles the seed-owned catalogue into:

```text
data/campusswap.db
```

The SQLite database is ignored by Git.

This means new or revised seeded listings are reconciled into the local database when the application restarts without duplicating existing items.

The demo currently contains 36 fictional listings across categories including study, electronics, furniture, sports, lifestyle, room essentials, books, and clothing.

There is no listing-management feature, so there is no user-created catalogue data to preserve.

Removing `data/campusswap.db` is optional. If removed, the application creates a fresh local database from the seeded catalogue on the next startup.

---

### Frontend

Vue 3 is loaded directly from the unpkg CDN as a native browser ES module.

There is no Vite, npm, or frontend build step.

`app/static/js/app.js` imports Vue and uses `createApp()` for the application roots.

Vue renders fetched catalogue data using escaped template interpolation.

The interface is responsive and designed to work on both desktop and mobile.

The main navigation provides:

- Browse
- Ask AI ✦
- Project notes

Ask AI is also accessible through a floating AI button on the main browsing, listing-detail, and project-notes pages so the AI feature is easy to discover.

---

## Marketplace search

The Browse page provides one unified search box.

Users can enter an exact item name or describe what they need in natural language. They do not need to choose between keyword and semantic search modes.

For example, a user could search for:

```text
desk lamp
```

or describe a need such as:

```text
something useful for studying at night
```

Any non-empty Browse query calls:

```text
/api/semantic-listings
```

The backend uses:

```text
openai/text-embedding-3-small
```

through the CognitioLabs OpenRouter-compatible route.

It compares the query embedding against the existing catalogue embeddings using cosine similarity.

The current demo uses:

- `0.30` as the starting similarity threshold
- a maximum of five returned listings

The `0.30` threshold is an empirically chosen starting point from testing the current 36-item seeded catalogue. It is not intended to be a universal relevance threshold.

An empty search calls:

```text
/api/listings
```

and displays the normal catalogue without making an embedding request.

A literal, case-insensitive keyword API remains available through:

```text
/api/listings?q=...
```

but the public Browse experience uses semantic retrieval for non-empty queries.

---

## Embedding cache

The backend sends embedding requests to the CognitioLabs OpenRouter-compatible embedding route using:

```text
openai/text-embedding-3-small
```

The gateway key is read only from the server-side `CLASSGW_KEY` environment variable.

Listing vectors are cached in SQLite using the:

```text
listing_embeddings
```

table.

Startup keeps vectors for unchanged indexed text and removes stale vectors when required.

New or changed listings are embedded lazily when an applicable semantic search requires them.

No separate vector database is used because the current catalogue is intentionally small.

---

## Browse and listing navigation

Browse filters are represented in the URL and respond to browser back and forward navigation.

Listing links preserve the current whitelisted:

```text
q
category
```

parameters.

When a user opens a listing from filtered Browse results, the detail page can return them to the same results.

Unfiltered listing links return to the normal Browse page.

Only local Browse URLs are reconstructed from the allowed query and category fields.

---

## Ask AI

Ask AI is available at:

```text
/ask
```

and is backed by:

```text
POST /api/catalogue-qa
```

Search and Ask AI serve different purposes:

- Search helps users **find relevant listings**.
- Ask AI helps users **understand, compare, and ask questions about the catalogue**.

Ask AI uses the same cached `openai/text-embedding-3-small` retrieval to relevance-order the catalogue.

It then sends the user's question together with compact, explicit catalogue records to:

```text
gpt-5.6-terra
```

through the CognitioLabs OpenAI-compatible gateway.

---

## Q&A grounding

Ask AI is designed to answer from the seeded CampusSwap catalogue rather than general knowledge.

Because the current demo contains only 36 listings, the backend provides the model with compact information for the full catalogue after relevance-ordering the records using embeddings.

Using the full small catalogue is intentional.

A small semantic Top-K context could accidentally leave out an item that matters for questions involving explicit facts such as price, condition, or pickup location.

If the catalogue becomes significantly larger, this approach would need to be revisited.

The model is instructed to:

- use only the supplied catalogue records
- compare only information explicitly available in those records
- avoid inventing missing product information
- acknowledge when the catalogue does not provide a requested fact

For example, if a listing does not provide information about warranty, delivery, or current stock availability, Ask AI should state that the catalogue does not contain that information instead of inventing an answer.

---

## Q&A listing validation

The answer model can return concise answer text together with candidate listing IDs.

Those IDs are treated as untrusted model output.

Before sending any listing card to the browser, the backend:

1. validates the candidate ID against the grounded catalogue
2. reloads the actual listing from SQLite
3. returns the validated record to the frontend

This allows the language model to help identify relevant listings while keeping the actual marketplace records under application control.

Clickable listing cards default to at most eight results.

When a question explicitly requests all matching items, the application can return all validated matches.

---

## Ask AI navigation state

Ask AI listing cards use links in the form:

```text
/listings/{id}?from=ask
```

When a user follows one of these cards, the listing detail page can return them to Ask AI.

The browser uses `sessionStorage` only to preserve the visible Ask AI session, including:

- user questions
- AI answers
- validated listing-card fields
- the `has_more` state

It does not store:

- API keys
- internal prompts
- embedding vectors
- similarity scores
- gateway details
- internal errors
- server-side chat history

This allows the visible conversation to be restored without exposing server-side information.

---

## Prices and filtering

Prices are stored using integer cents and displayed in SGD.

Category matching is exact.

The legacy keyword API performs literal, case-insensitive title and description matching, while the public Browse interface uses semantic search for non-empty queries.

---

## Development approach

I approached the assessment by first identifying the main user journey:

```text
Browse → Search → Listing → Ask AI → Relevant listing
```

I first built the basic seeded marketplace, category filtering, and listing pages.

I then considered how students might search. Exact keyword matching works when a user already knows the item name, but it becomes limited when someone describes a need instead. This led to adding embedding-based semantic search.

I later simplified the interface into one unified search box because users should not need to understand or select technical search modes.

After search was working, I designed Ask AI to solve a different problem: helping users understand and compare the catalogue rather than simply retrieving listings.

Grounding and backend validation were then added to reduce unsupported AI responses and keep real listing data controlled by the application.

Finally, I reviewed the experience from the perspective of a normal user and an assessment reviewer. This led to improvements in navigation state, AI discoverability, responsive behaviour, and deployed testing.

Larger marketplace features were intentionally left out so the project could stay focused on the assessment's core marketplace, AI, grounding, testing, and deployment requirements.

The public `/notes` page contains a more detailed explanation of the development process and design decisions.

---

## AI-assisted development

I used Codex as an AI coding tool during development.

It was used to help:

- inspect the repository
- plan parts of the implementation
- write and review application code
- investigate implementation issues
- improve project documentation

AI-assisted development was used as part of the engineering workflow rather than as a replacement for testing and verification.

Important implementation changes were reviewed and tested before being committed.

---

## Project notes

The public Project Notes page is available at:

```text
/notes
```

It documents:

- what CampusSwap is and who it is for
- the development and thinking process
- which data is seeded or simulated
- the AI coding tools and models used
- grounding and technical decisions
- intentionally omitted features
- testing performed
- known issues and limitations

The notes should be updated alongside important feature changes so they continue to describe the actual state of the demo.

---

## Checks

Install the development requirements:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Run the automated test suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use a temporary SQLite database and mock embedding and chat-completion calls.

This keeps catalogue and cache assertions deterministic and makes zero real gateway requests during the automated test suite.

The tests cover areas including:

- seed reconciliation
- keyword and category filtering
- literal inputs
- validation
- missing listings
- pages and static assets
- categories
- semantic filtering
- embedding caching
- grounded Q&A context construction
- comparisons
- missing-fact responses
- SQLite validation of Q&A listing IDs
- default card limits
- explicit all-results requests
- safe external-service error responses

The deployed site has also been tested manually in a desktop browser and on a mobile phone.

---

## Current limits

All sellers, listings, prices, conditions, and Singapore pickup locations are fictional examples created for the assessment.

Emoji are used as image placeholders.

The following production marketplace features are intentionally not implemented:

- accounts and authentication
- identity or campus verification
- payments
- seller messaging
- listing management
- image uploads
- stock tracking
- persistent chat history
- streaming chat
- real transactions

Ask AI answers from the supplied seeded-catalogue context. Its grounding instructions and backend validation reduce unsupported answers, but the feature has not been fully evaluated against adversarial prompts.

Non-empty semantic search and Ask AI require a valid server-side `CLASSGW_KEY`, access to the CognitioLabs gateway, and seeded SQLite listings. Gateway errors are reported generically to users.

The application is deployed as an assessment demo rather than a production marketplace.

SQLite is suitable for this small seeded catalogue but requires a writable local disk and is not designed here for multi-server production use.

There is currently no pagination or sorting control.

Browse and listing pages require JavaScript and network access to the Vue CDN.

The deployed website has been tested in a desktop browser and on a mobile phone. A full accessibility and assistive-technology review has not been completed.

See the public `/notes` page for the full project state, development approach, design decisions, and known limitations.