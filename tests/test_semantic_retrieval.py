# tests/test_semantic_retrieval.py

"""
Tests for the Phase 14a semantic retrieval core.

Unlike every other AI-related test in this project, these need NO
mocking at all. sentence-transformers runs a real local embedding
model deterministically — the same text always produces the same
vector — so real assertions against real similarity scores are both
possible and meaningful here in a way they aren't for a
non-deterministic LLM call.

Every threshold value asserted below comes from an actual diagnostic
run against retrieval/corpus.py (scripts/semantic_retrieval_diagnostic.py),
not from assumption. Margins are set comfortably inside the real
observed gap between true-positive and true-negative scores, not
pinned to the exact observed value, so the tests aren't flaky against
tiny, harmless variation from library version changes.

Requires real internet access on first run (downloads the model, one
time, then caches locally) — this is NOT run in CI, since CI currently
only runs eval/run_eval.py, not the full pytest suite.
"""

from retrieval.semantic_search import DEFAULT_SIMILARITY_THRESHOLD, find_semantic_matches


def test_close_wording_query_matches_correct_record():
    matches = find_semantic_matches("ABB circuit breaker 10 amp DIN rail")
    assert len(matches) > 0
    assert matches[0].manufacturer == "ABB"
    assert "circuit breaker" in matches[0].matched_description.lower()
    assert matches[0].similarity_score > 0.8


def test_paraphrase_without_brand_still_finds_correct_record():
    """
    The actual point of semantic retrieval over keyword/manufacturer
    search: no brand mentioned at all, yet the correct historical
    record still surfaces as the top match.
    """
    matches = find_semantic_matches(
        "circuit breaker, 10 amp rating, mounts on DIN rail"
    )
    assert len(matches) > 0
    assert matches[0].manufacturer == "ABB"
    assert matches[0].similarity_score > 0.7


def test_discriminates_schneider_from_abb_by_manufacturer_language():
    """
    Two near-duplicate circuit breaker records exist (ABB and
    Schneider). A query naming Schneider must rank the Schneider
    record above the ABB one — real run: 0.8373 vs 0.4669.
    """
    matches = find_semantic_matches("Schneider circuit breaker 16A")
    assert len(matches) > 0
    assert matches[0].manufacturer == "Schneider Electric"
    assert len(matches) < 2 or matches[0].similarity_score > matches[1].similarity_score


def test_discriminates_flowserve_from_john_crane_pump_seals():
    """
    Same discrimination test, different near-duplicate pair (pump
    mechanical seals from two different manufacturers) — real run:
    Flowserve 0.7702 vs John Crane 0.6051.
    """
    matches = find_semantic_matches("Flowserve mechanical seal for pump")
    assert len(matches) > 0
    assert matches[0].manufacturer == "Flowserve"


def test_same_manufacturer_does_not_cause_false_match_on_wrong_product():
    """
    ABB appears in two unrelated corpus records (a circuit breaker and
    a VFD drive). A VFD drive query must match the VFD record, not the
    breaker record, despite sharing a manufacturer — real run: VFD
    record 0.5833 vs breaker record 0.3391.
    """
    matches = find_semantic_matches("ABB variable frequency drive 22kW")
    assert len(matches) > 0
    assert "drive" in matches[0].matched_description.lower()
    assert "breaker" not in matches[0].matched_description.lower()


def test_true_negative_returns_no_matches():
    """
    A query entirely unrelated to procurement must return nothing
    above threshold — real run: top score 0.0710. Guessing a
    plausible-looking but wrong supplier is worse than correctly
    finding nothing.
    """
    matches = find_semantic_matches("birthday cake recipe with chocolate frosting")
    assert matches == []


def test_true_negative_procurement_adjacent_still_returns_no_matches():
    """
    A harder true negative: office furniture is at least superficially
    "procurement-shaped" text, but nothing in this industrial-parts
    corpus is actually similar to it — real run: top score 0.1341.
    """
    matches = find_semantic_matches("need pricing for office chairs and desks")
    assert matches == []


def test_threshold_default_has_real_margin_on_both_sides():
    """
    Documents WHY 0.5 was chosen, from actual measured data: every
    true-positive top score observed was >= 0.58, every true-negative
    top score observed was <= 0.14. 0.5 sits inside that real gap.
    """
    assert DEFAULT_SIMILARITY_THRESHOLD == 0.5
