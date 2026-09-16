# scripts/semantic_retrieval_diagnostic.py

"""
One-off diagnostic — NOT part of the test suite. Prints raw
similarity scores (threshold disabled) for every planned test query,
so the actual threshold and pass/fail assertions in
tests/test_semantic_retrieval.py can be set from real numbers instead
of a guess.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.semantic_search import find_semantic_matches

queries = [
    ("close wording", "ABB circuit breaker 10 amp DIN rail"),
    ("paraphrase, no brand", "circuit breaker, 10 amp rating, mounts on DIN rail"),
    ("discrimination: Schneider not ABB", "Schneider circuit breaker 16A"),
    ("discrimination: Flowserve not John Crane", "Flowserve mechanical seal for pump"),
    ("true negative", "birthday cake recipe with chocolate frosting"),
    ("true negative 2 (procurement-adjacent but unrelated)", "need pricing for office chairs and desks"),
    ("same manufacturer, different product", "ABB variable frequency drive 22kW"),
]

for label, q in queries:
    print(f"--- {label} ---")
    print(f"Query: {q!r}")
    matches = find_semantic_matches(q, top_k=3, threshold=0.0)  # threshold disabled — show everything
    for m in matches:
        print(f"  {m.similarity_score:.4f}  {m.manufacturer!r:25} {m.matched_description}")
    print()