import json
from pathlib import Path
from typing import List, Dict, Any

from sentence_transformers import SentenceTransformer, util


HISTORICAL_PATH = Path("mock_data/historical_supplier_items.json")
TEST_ITEMS_PATH = Path("mock_data/ai_test_rfq_items.json")

TOP_K = 3
SIMILARITY_THRESHOLD = 0.65


def load_json(path: Path) -> List[Dict[str, Any]]:
    """Load JSON file and return as list"""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_embedding_model():
    """Load sentence-transformer model once at startup"""
    try:
        print("Loading embedding model...")
        model = SentenceTransformer("all-MiniLM-L6-v2")
        print("✅ Embedding model loaded.")
        return model
    except Exception as e:
        print(f"❌ Failed to load embedding model: {e}")
        return None


def get_embeddings(
    model: SentenceTransformer,
    texts: List[str]
) -> List[List[float]]:
    """Convert list of texts to embeddings using local model"""
    embeddings = model.encode(texts, convert_to_tensor=True)
    return embeddings


def build_text(item: Dict[str, Any]) -> str:
    """Build a single text string from item fields for embedding"""
    parts = [
        item.get("category", ""),
        item.get("manufacturer", ""),
        item.get("part_number") or "",
        item.get("description", ""),
    ]
    return " | ".join(part for part in parts if part)


def suggest_suppliers(
    test_item: Dict[str, Any],
    historical_items: List[Dict[str, Any]],
    historical_embeddings,
    model: SentenceTransformer,
) -> List[Dict[str, Any]]:
    """Suggest suppliers based on semantic similarity"""

    # Guardrail: branded equipment should prioritize manufacturer/distributor logic
    if test_item.get("category") == "branded_equipment":
        return [
            {
                "note": "AI similarity skipped — branded equipment. Prioritize manufacturer/distributor sourcing.",
                "category": test_item.get("category"),
                "manufacturer": test_item.get("manufacturer"),
            }
        ]

    # Build and embed the test item text
    test_text = build_text(test_item)
    test_embedding = get_embeddings(model, [test_text])

    scored_results = []

    for hist_item, hist_embedding in zip(historical_items, historical_embeddings):
        # Use built-in cosine similarity
        score = util.cos_sim(test_embedding, hist_embedding).item()

        if score >= SIMILARITY_THRESHOLD:
            scored_results.append(
                {
                    "supplier_name": hist_item["supplier_name"],
                    "supplier_email": hist_item["supplier_email"],
                    "similarity_score": round(score, 4),
                    "reason": f"Similar to historical item: {hist_item['description']}",
                    "evidence_tags": [
                        "description_match",
                        hist_item.get("evidence", "historical_record"),
                        hist_item.get("priority", "unknown_priority"),
                    ],
                    "historical_item_id": hist_item["historical_item_id"],
                    "human_review_required": True,
                }
            )

    # Sort by similarity score descending
    scored_results.sort(key=lambda x: x["similarity_score"], reverse=True)

    return scored_results[:TOP_K]


def main() -> None:
    # Step 1 — Load embedding model first
    model = load_embedding_model()
    if model is None:
        return

    # Step 2 — Load data
    historical_items = load_json(HISTORICAL_PATH)
    test_items = load_json(TEST_ITEMS_PATH)

    # Step 3 — Embed all historical items once
    historical_texts = [build_text(item) for item in historical_items]
    historical_embeddings = get_embeddings(model, historical_texts)

    # Step 4 — Process each test item
    for test_item in test_items:
        print("\n" + "=" * 80)
        print(f"Test case:   {test_item['test_case_id']}")
        print(f"Category:    {test_item['category']}")
        print(f"Description: {test_item['description']}")
        print(f"Expected:    {test_item['expected_behavior']}")

        suggestions = suggest_suppliers(
            test_item,
            historical_items,
            historical_embeddings,
            model,
        )

        print("\nAI Supplier Suggestions:")

        if not suggestions:
            print("  No confident supplier suggestion found.")
            continue

        for idx, suggestion in enumerate(suggestions, start=1):
            if "note" in suggestion:
                print(f"  {idx}. ⚠️  {suggestion['note']}")
                continue

            print(f"  {idx}. Supplier:    {suggestion['supplier_name']}")
            print(f"     Email:       {suggestion['supplier_email']}")
            print(f"     Similarity:  {suggestion['similarity_score']}")
            print(f"     Reason:      {suggestion['reason']}")
            print(f"     Evidence:    {suggestion['evidence_tags']}")
            print(f"     Review:      Human review required")


if __name__ == "__main__":
    main()