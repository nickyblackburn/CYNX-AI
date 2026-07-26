#!/usr/bin/env python3
"""Quick validation test for the refactored web_search tool."""

import sys
sys.path.insert(0, '.')

from tools.web_search import (
    SearchIntent, OutputMode, _build_intent, _build_search_query,
    ResultFilter, ResultRanker, _format_result
)

def test_intent_detection():
    print("=" * 60)
    print("TEST 1: Intent Detection - Normal query")
    print("=" * 60)
    intent = _build_intent("best phones to buy")
    print(f"Subject: {intent.subject}")
    print(f"Output Type: {intent.output_type}")
    print(f"Is Adult: {intent.is_adult_search}")
    print(f"Modifiers: {intent.modifiers}")
    assert intent.output_type == OutputMode.LIST
    print("✓ PASSED\n")

def test_position_query():
    print("=" * 60)
    print("TEST 2: Intent Detection - Position query")
    print("=" * 60)
    intent = _build_intent("sex positions guide")
    print(f"Subject: {intent.subject}")
    print(f"Output Type: {intent.output_type}")
    print(f"Query Terms: {intent.query_terms}")
    assert intent.output_type == OutputMode.POSITIONS
    assert intent.is_adult_search == True
    print("✓ PASSED\n")

def test_list_query():
    print("=" * 60)
    print("TEST 3: Intent Detection - List query")
    print("=" * 60)
    intent = _build_intent("best keyboards")
    print(f"Subject: {intent.subject}")
    print(f"Output Type: {intent.output_type}")
    assert intent.output_type == OutputMode.LIST
    print("✓ PASSED\n")

def test_search_query_building():
    print("=" * 60)
    print("TEST 4: Search Query Building")
    print("=" * 60)
    intent = _build_intent("best vibrator for couples reviews")
    search_query = _build_search_query(intent)
    print(f"Original: {intent.subject}")
    print(f"Search Query: {search_query}")
    assert len(search_query) > 0
    assert "vibrator" in search_query
    print("✓ PASSED\n")

def test_filtering():
    print("=" * 60)
    print("TEST 5: Result Filtering")
    print("=" * 60)
    filter_pipeline = ResultFilter()
    test_cases = [
        ("Valid Title", "Valid body", "https://example.com", False),
        ("", "Empty title", "https://example.com", True),
        ("Title", "body", "javascript:alert()", True),
        ("Makeup product", "body", "https://example.com", True),
    ]
    for title, body, href, expected_bad in test_cases:
        is_bad = filter_pipeline.is_bad_result(title, body, href)
        status = "✓" if is_bad == expected_bad else "✗"
        print(f"{status} Title: {title!r:20} | Bad: {is_bad} (expected: {expected_bad})")
        assert is_bad == expected_bad
    print("✓ PASSED\n")

def test_ranking():
    print("=" * 60)
    print("TEST 6: Result Ranking")
    print("=" * 60)
    intent = _build_intent("best sex position guide")
    ranker = ResultRanker(intent)
    results = [
        ("The Ultimate Guide to Sex Positions", "Complete guide with illustrations", "https://example.com/guide"),
        ("Random Article", "Nothing related", "https://example.com/random"),
        ("Best Positions for Couples", "Tips and techniques", "https://example.com/positions"),
    ]
    scores = []
    for title, body, href in results:
        score = ranker.rank(title, body, href)
        scores.append(score)
        print(f"Score: {score:3d} | {title}")
    
    # Position-related results should score higher
    assert scores[0] > scores[1], "Position guide should score higher than random article"
    assert scores[2] > scores[1], "Position article should score higher than random article"
    print("✓ PASSED\n")

def test_fursuit_query():
    print("=" * 60)
    print("TEST 7: Fursuit Query Intent")
    print("=" * 60)
    intent = _build_intent("best fursuit makers")
    print(f"Subject: {intent.subject}")
    print(f"Output Type: {intent.output_type}")
    print(f"Modifiers: {intent.modifiers}")
    print(f"Context Keywords: {intent.context_keywords}")
    assert "fursuit" in str(intent.modifiers) or "fursuit" in intent.context_keywords
    print("✓ PASSED\n")

def test_backward_compatibility():
    print("=" * 60)
    print("TEST 8: Backward Compatibility Check")
    print("=" * 60)
    intent = _build_intent("search something")
    search_query = _build_search_query(intent)
    print(f"Query: {search_query}")
    
    # Verify we can still create filter and ranker
    filter_obj = ResultFilter()
    ranker_obj = ResultRanker(intent)
    
    # Test basic filtering and ranking
    is_bad = filter_obj.is_bad_result("Title", "Body", "https://example.com")
    score = ranker_obj.rank("Title", "Body", "https://example.com")
    
    print(f"Filter works: {isinstance(is_bad, bool)}")
    print(f"Ranker works: {isinstance(score, int)}")
    assert isinstance(is_bad, bool)
    assert isinstance(score, int)
    print("✓ PASSED\n")

if __name__ == "__main__":
    try:
        test_intent_detection()
        test_position_query()
        test_list_query()
        test_search_query_building()
        test_filtering()
        test_ranking()
        test_fursuit_query()
        test_backward_compatibility()
        
        print("=" * 60)
        print("✓✓✓ ALL VALIDATION TESTS PASSED ✓✓✓")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
