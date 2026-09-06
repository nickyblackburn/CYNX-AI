from benchmark.runner import BenchmarkStorage
import json

s = BenchmarkStorage()

# Simulate a result with invalid filename characters
result1 = {
    "test_id": "test:one/<>\\|?*",
    "category": "personality_preservation",
    "behavior_tags": ["suiteA"],
    "response_time_seconds": 1.23,
    "response_words": 10,
    "scores": {"overall": 8},
}

# Simulate another result with same test_id to check collision handling
result2 = result1.copy()
result2["test_id"] = "test:one/<>\\|?*"
result2["scores"] = {"overall": 7}

# Simulate a third distinct result
result3 = {
    "test_id": "normal_test_3",
    "category": "emotion",
    "behavior_tags": ["suiteB"],
    "response_time_seconds": 0.5,
    "response_words": 5,
    "scores": {"overall": 9},
}

s.add(result1)
print('Added result1')
s.add(result2)
print('Added result2')
s.add(result3)
print('Added result3')

s.save_summary()
print('Saved summary')

print('Run file written to:', s.run_file)
