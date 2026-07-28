import json
from pathlib import Path

import matplotlib.pyplot as plt


RESULTS = Path("results/results.json")


with open(
    RESULTS,
    "r",
    encoding="utf-8"
) as f:

    data = json.load(f)


ids = []
times = []

for result in data:

    ids.append(result["test_id"])
    times.append(result["response_time_seconds"])


print("\n========== BENCHMARK ==========\n")

print(f"Tests: {len(data)}")

print(f"Average Response: {sum(times)/len(times):.2f}s")

print(f"Fastest: {min(times):.2f}s")

print(f"Slowest: {max(times):.2f}s")

print()

for result in data:

    print(
        f"{result['test_id']} | "
        f"{result['category']:<18} | "
        f"{result['response_time_seconds']:.2f}s"
    )


plt.figure(figsize=(12,5))

plt.plot(
    ids,
    times,
    marker="o"
)

plt.title("CYN-X Benchmark Response Time")

plt.xlabel("Test ID")

plt.ylabel("Seconds")

plt.grid(True)

plt.tight_layout()

plt.show()