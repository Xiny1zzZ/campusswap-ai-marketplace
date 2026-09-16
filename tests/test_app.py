import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError
from fastapi.testclient import TestClient
from app import catalogue_qa, database, semantic_search
from app.main import app


class MarketplaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patched = patch.object(database, "DB_PATH", Path(self.temp.name) / "test.db")
        patched.start()
        self.addCleanup(patched.stop)
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_seed_is_not_duplicated(self):
        items = self.client.get("/api/listings").json()
        self.assertEqual(len(items), 36)
        self.assertTrue(any(item["price_cents"] == 0 for item in items))
        database.initialize()
        self.assertEqual(self.client.get("/api/listings").json(), items)

    def test_combined_filters(self):
        items = self.client.get("/api/listings", params={"q": "  KEYBOARD  ", "category": "Electronics"}).json()
        self.assertEqual([item["id"] for item in items], [3, 20])
        self.assertEqual(len(self.client.get("/api/listings", params={"category": "Books"}).json()), 3)
        self.assertEqual(self.client.get("/api/listings", params={"q": "keyboard", "category": "Books"}).json(), [])
        self.assertEqual([item["id"] for item in self.client.get("/api/listings", params={"q": "AAA"}).json()], [3])

    def test_literal_inputs(self):
        for keyword in ["%", "_", "' OR 1=1 --", "does-not-exist"]:
            self.assertEqual(self.client.get("/api/listings", params={"q": keyword}).json(), [])
        self.assertEqual(self.client.get("/api/listings", params={"q": "a" * 201}).status_code, 422)

    def test_detail_and_missing(self):
        self.assertEqual(self.client.get("/api/listings/1").json()["id"], 1)
        self.assertEqual(self.client.get("/api/listings/999").status_code, 404)
        self.assertEqual(self.client.get("/listings/999").status_code, 404)
        self.assertEqual(self.client.get("/api/listings/not-an-id").status_code, 422)

    def test_pages_assets_categories(self):
        for path in ["/", "/ask", "/notes", "/listings/1", "/static/css/styles.css", "/static/js/app.js"]:
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.assertEqual(len(self.client.get("/api/categories").json()), 8)
        self.assertIn("openai/text-embedding-3-small", self.client.get("/notes").text)
        browse_page = self.client.get("/").text
        browse_script = self.client.get("/static/js/app.js").text
        self.assertIn("Ask CampusSwap", browse_page)
        self.assertIn("Search CampusSwap", browse_page)
        self.assertIn("Search an item or describe what you need...", browse_page)
        self.assertIn("Search by item name or describe what you’re looking for.", browse_page)
        self.assertIn('/static/css/styles.css?v=sticky-header-1', browse_page)
        self.assertIn('/static/js/app.js?v=browse-nav-2', browse_page)
        self.assertIn(':href="listingHref(item.id)"', browse_page)
        self.assertNotIn("search-mode", browse_page)
        self.assertNotIn("Search type", browse_page)
        self.assertNotIn("searchMode", browse_script)
        self.assertNotIn("semantic', '1", browse_script)
        self.assertIn("keyword.value.trim() ? '/api/semantic-listings' : '/api/listings'", browse_script)
        ask_page = self.client.get("/ask").text
        notes_page = self.client.get("/notes").text
        ask_script = self.client.get("/static/js/app.js?v=ask-nav-5").text
        detail_page = self.client.get("/listings/1?from=browse&q=calculator&category=Electronics").text
        self.assertIn('/static/js/app.js?v=ask-nav-5', ask_page)
        self.assertIn('/static/css/styles.css?v=sticky-header-1', ask_page)
        self.assertIn('/static/css/styles.css?v=sticky-header-1', notes_page)
        self.assertIn('What can I get for studying under $30?', ask_script)
        self.assertIn('<section v-if="!messages.length" class="example-prompts"', ask_page)
        self.assertIn('@keydown.enter.exact.prevent="submit"', ask_page)
        self.assertIn("function askExample(prompt)", ask_script)
        self.assertIn("listings: result.listings || []", ask_script)
        self.assertIn("examples, price, submit, askExample", ask_script)
        self.assertIn('class="qa-listing-card"', ask_page)
        self.assertIn(':href="`/listings/${item.id}?from=ask`"', ask_page)
        self.assertIn("if (document.querySelector('#ask-app')) askApp();", ask_script)
        self.assertIn("sessionStorage.setItem(ASK_CONVERSATION_KEY", ask_script)
        self.assertIn("const fromAsk = from === 'ask'", browse_script)
        self.assertIn("const backHref = fromAsk ? '/ask'", browse_script)
        self.assertIn(':href="backHref"', detail_page)
        self.assertIn('/static/css/styles.css?v=sticky-header-1', detail_page)
        self.assertIn('/static/js/app.js?v=detail-nav-1', detail_page)
        self.assertNotIn("CLASSGW_KEY", ask_script)
        self.assertNotIn("SYSTEM_PROMPT", ask_script)

    def test_semantic_search_caches_only_catalogue_listings(self):
        def fake_embeddings(inputs):
            return [[1.0, 0.0] for _ in inputs]

        with patch.dict(os.environ, {"CLASSGW_KEY": "test-key"}), \
             patch("app.semantic_search.request_embeddings", side_effect=fake_embeddings) as gateway:
            response = self.client.get("/api/semantic-listings", params={"q": "something for studying", "category": "Electronics"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [3, 7, 15, 16, 17])
        self.assertLessEqual(len(response.json()), semantic_search.MAX_RESULTS)
        self.assertEqual(database.embedding_count(), 8)
        self.assertEqual(gateway.call_count, 2)

    def test_semantic_search_excludes_scores_below_threshold(self):
        def fake_embeddings(inputs):
            if inputs == ["nothing in this catalogue"]:
                return [[-1.0, 0.0]]
            return [[1.0, 0.0] for _ in inputs]

        with patch.dict(os.environ, {"CLASSGW_KEY": "test-key"}), \
             patch("app.semantic_search.request_embeddings", side_effect=fake_embeddings):
            response = self.client.get("/api/semantic-listings", params={"q": "nothing in this catalogue", "category": "Sports"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_seed_reconciliation_adds_new_rows_and_invalidates_stale_vectors(self):
        original = database.get_listing(1)
        database.save_embedding(1, "test-model", "outdated indexed text", [1.0, 0.0])
        self.assertEqual(database.embedding_count(), 1)
        with database.connect() as db:
            db.execute("DELETE FROM listings WHERE id = 36")

        database.initialize()

        self.assertEqual(database.get_listing(1), original)
        self.assertEqual(len(database.browse()), 36)
        self.assertEqual(database.get_listing(36)["title"], "Laptop sleeve, 13 inch")
        self.assertEqual(database.embedding_count(), 0)

    def test_semantic_search_handles_missing_key_and_gateway_failure(self):
        with patch.dict(os.environ, {}, clear=True):
            missing_key = self.client.get("/api/semantic-listings", params={"q": "desk item"})
        self.assertEqual(missing_key.status_code, 503)
        self.assertNotIn("CLASSGW_KEY", missing_key.text)

        with patch.dict(os.environ, {"CLASSGW_KEY": "test-key"}), \
             patch("app.semantic_search.request_embeddings", side_effect=semantic_search.SemanticSearchUnavailable("gateway secret detail")):
            unavailable = self.client.get("/api/semantic-listings", params={"q": "desk item"})
        self.assertEqual(unavailable.status_code, 503)
        self.assertNotIn("gateway secret detail", unavailable.text)

    def test_catalogue_qa_builds_grounded_context_from_all_seeded_listings(self):
        ranked = [(1.0, item) for item in database.browse()]
        with patch("app.semantic_search.rank_catalogue", return_value=ranked) as retrieval, \
             patch("app.catalogue_qa.request_answer", return_value={
                 "answer": "The Scientific calculator is cheaper.", "listing_ids": [7, 999, 7],
             }) as chat:
            result = catalogue_qa.answer("Which calculator is cheaper?")

        records = chat.call_args.args[1]
        self.assertEqual(result["answer"], "The Scientific calculator is cheaper.")
        self.assertEqual([item["id"] for item in result["listings"]], [7])
        self.assertFalse(result["has_more"])
        self.assertEqual(len(records), 36)
        self.assertEqual(records[0]["id"], 1)
        self.assertEqual(set(records[0]), {"id", "title", "description", "category", "price_cents", "price_sgd", "condition", "location", "seller"})
        self.assertNotIn("icon", records[0])
        retrieval.assert_called_once_with("Which calculator is cheaper?")

    def test_catalogue_qa_endpoint_returns_comparison_and_missing_fact_answers(self):
        with patch("app.catalogue_qa.answer", side_effect=[
            {"answer": "The Scientific calculator is cheaper at SGD 14.00.",
             "listings": [database.get_listing(7), database.get_listing(12)], "has_more": False},
            {"answer": "The seeded catalogue does not provide warranty information.",
             "listings": [], "has_more": False},
        ]) as answer:
            comparison = self.client.post("/api/catalogue-qa", json={"question": "Which calculator is cheaper?"})
            missing_fact = self.client.post("/api/catalogue-qa", json={"question": "Which item has the longest warranty?"})

        self.assertEqual(comparison.status_code, 200)
        self.assertIn("cheaper", comparison.json()["answer"])
        self.assertEqual([item["id"] for item in comparison.json()["listings"]], [7, 12])
        self.assertFalse(comparison.json()["has_more"])
        self.assertEqual(missing_fact.status_code, 200)
        self.assertIn("does not provide warranty", missing_fact.json()["answer"])
        self.assertEqual(answer.call_count, 2)

    def test_catalogue_qa_caps_cards_unless_all_is_requested(self):
        ranked = [(1.0, item) for item in database.browse()]
        model_response = {"answer": "Here are matching items.", "listing_ids": list(range(1, 11))}
        with patch("app.semantic_search.rank_catalogue", return_value=ranked), \
             patch("app.catalogue_qa.request_answer", return_value=model_response):
            default_result = catalogue_qa.answer("Show me study items")
            all_result = catalogue_qa.answer("Show all study items")

        self.assertEqual([item["id"] for item in default_result["listings"]], list(range(1, 9)))
        self.assertTrue(default_result["has_more"])
        self.assertEqual([item["id"] for item in all_result["listings"]], list(range(1, 11)))
        self.assertFalse(all_result["has_more"])

    def test_catalogue_qa_validation_and_safe_failures(self):
        self.assertEqual(self.client.post("/api/catalogue-qa", json={"question": "   "}).status_code, 422)
        self.assertEqual(self.client.post("/api/catalogue-qa", json={"question": "x" * 501}).status_code, 422)

        with patch.dict(os.environ, {}, clear=True):
            missing_key = self.client.post("/api/catalogue-qa", json={"question": "Compare calculators"})
        self.assertEqual(missing_key.status_code, 503)
        self.assertNotIn("CLASSGW_KEY", missing_key.text)

        with patch.dict(os.environ, {"CLASSGW_KEY": "test-key"}), \
             patch("app.catalogue_qa.urlopen", side_effect=URLError("gateway secret detail")):
            with self.assertRaises(catalogue_qa.CatalogueQAUnavailable):
                catalogue_qa.request_answer("Question", [{"id": 1}])

        with patch("app.catalogue_qa.answer", side_effect=catalogue_qa.CatalogueQAUnavailable("gateway secret detail")):
            unavailable = self.client.post("/api/catalogue-qa", json={"question": "Compare calculators"})
        self.assertEqual(unavailable.status_code, 503)
        self.assertNotIn("gateway secret detail", unavailable.text)


if __name__ == "__main__":
    unittest.main()
