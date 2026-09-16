# CampusSwap project rules

CampusSwap is an AI-enabled second-hand marketplace for students, built for the CognitioLabs Associate Forward Deployed Engineer assessment.

## Development workflow

- Develop the project step by step, following the user's requested scope.
- Use HTML, CSS, Vue 3 loaded as native ES modules from a CDN, and Python FastAPI as the proposed stack. Do not add a Node.js build step or frontend dependency tooling unless the user requests it. Architecture proposals are not implemented features.
- Semantic natural-language search uses embeddings, and Ask CampusSwap provides grounded catalogue Q&A. Do not add accounts, payments, messaging, persistent chat history, streaming, or other chatbot features until requested.
- Keep this file current when project rules change.

## Public /notes page

- Continuously maintain the public `/notes` page as the project develops.
- Whenever an important feature is added, modified, removed, simulated, completed, or found to have a limitation, update `/notes` in the same task.
- The page must accurately reflect the CURRENT state of the demo.
- Write in simple, natural first-person language that sounds like the project owner's own notes.
- Never claim that a simulated or unfinished feature is complete. Clearly distinguish implemented behavior from plans.
- Track all of the following:
  1. What I have built and who it is for.
  2. What is seeded, simulated, limited, or unfinished.
  3. Which AI coding tools I used.
  4. Which models power natural-language search and catalogue Q&A.
  5. Important technical and product decisions.
  6. What I intentionally chose not to build and why.
  7. Known issues.
  8. Unfinished parts and current limitations.
- Record tools and models only when their use is verified. Do not invent model names or confuse coding tools with models powering the application.
- If no model powers a feature yet, explicitly say that it is not implemented and no model is connected.
- Before finishing a feature task, check that `/notes` matches the actual demo, including any newly discovered limitations.

## Current implementation and scope

The initial MVP uses FastAPI, SQLite, HTML, CSS, and Vue 3. Vue is imported from the unpkg CDN as a native ES module in app/static/js/app.js; that module calls createApp() for the browse, listing-detail, and Ask CampusSwap page roots. It provides a responsive browse page, listing detail pages, unified semantic search with category filtering, grounded catalogue Q&A, and public /notes at app/pages/notes.html. Thirty-six fictional student-marketplace listings are seed-owned demo data. On startup, the application reconciles this catalogue into SQLite by stable ID, so an existing local demo database receives seed additions and revisions without duplicates.

The browse UI provides one unified search box backed by natural-language retrieval: users can enter an item name or describe what they need without choosing a mode. A non-empty query uses `openai/text-embedding-3-small` through the CognitioLabs OpenRouter gateway. The server reads `CLASSGW_KEY` only from its environment and stores cached vectors in the local SQLite `listing_embeddings` table; there is no vector database. Startup preserves vectors whose indexed title, description, category, and condition text is unchanged, and invalidates stale entries; vectors for new listings are made lazily during an applicable natural-language search. Results below cosine similarity `0.30` are excluded and at most five are returned. An empty browse query shows the normal catalogue without requesting embeddings. The literal, case-insensitive `/api/listings?q=...` keyword API remains available, but users do not select it in the UI. The `0.30` threshold is an empirically chosen starting point from testing the current 36-item seeded catalogue, not a universal relevance threshold.

Ask CampusSwap is separate from the unified browse search at `/ask` and uses `POST /api/catalogue-qa`. It relevance-orders all 36 listings with the existing cached embedding retrieval, then sends compact explicit SQLite fields for every listing and the question to `gpt-5.6-terra` via the CognitioLabs OpenAI-compatible gateway. Full-catalogue context is intentional while the demo is small because price and pickup-location facts could be omitted by semantic Top-K retrieval. The model returns concise text plus untrusted candidate listing IDs; the server validates IDs against both the grounded context and SQLite before returning real listing records for cards. Cards default to eight or fewer, while explicit all-results wording can return all validated matches. The system instruction requires answers to use only supplied records and explicitly acknowledge unavailable facts. `CLASSGW_KEY`, prompts, embeddings, scores, gateway details, and internal failures must never reach the browser. Missing keys and gateway failures return generic errors. Accounts, authentication, payments, messaging, listing management, persistent chat history, streaming, and other chatbot features are not implemented. Codex has been used for planning, implementation, documentation, and checks.

Browse listing links preserve only whitelisted local `q` and `category` parameters and listing detail reconstructs only a local Browse or results URL. Ask listing links use `from=ask`; the browser uses sessionStorage to restore only visible Ask questions, answers, validated card fields, and `has_more`. It must never store credentials, prompts, embeddings, scores, errors, or gateway details, and must not allow arbitrary redirect destinations.

Run checks with python -m unittest discover -s tests -v after installing requirements-dev.txt. Tests use a temporary SQLite database. See README.md for startup instructions and limitations.
