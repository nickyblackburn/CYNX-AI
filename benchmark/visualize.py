import json
from pathlib import Path
from datetime import datetime

import matplotlib.pyplot as plt


RESULTS_DIR = Path(
    "results"
)


def load_history():

    files = sorted(
        RESULTS_DIR.glob(
            "cynx_benchmark_*.json"
        )
    )

    history = []

    for file in files:

        with open(
            file,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        history.append(
            {
                "file": file.name,
                "data": data
            }
        )

    return history



history = load_history()


if not history:

    print(
        "No benchmark history found"
    )

    exit()



print()
print("=" * 70)
print("CYN-X BENCHMARK HISTORY")
print("=" * 70)



runs = []

for run in history:

    data = run["data"]

    scores = {
        "personality": [],
        "reasoning": [],
        "emotional": [],
        "creativity": [],
        "safety": [],
        "memory": [],
        "overall": []
    }


    times = []
    tokens = []
    words = []


    for result in data:

        times.append(
            result["response_time_seconds"]
        )

        tokens.append(
            result.get(
                "estimated_tokens",
                0
            )
        )

        words.append(
            result.get(
                "response_words",
                0
            )
        )


        result_scores = result.get(
            "scores",
            {}
        )


        for key in scores:

            if key in result_scores:

                scores[key].append(
                    result_scores[key]
                )



    averages = {}

    for key, values in scores.items():

        if values:

            averages[key] = round(
                sum(values) / len(values),
                2
            )

        else:

            averages[key] = 0



    run_info = {

        "name": run["file"],

        "tests": len(data),

        "response_time":
            round(
                sum(times)/len(times),
                2
            ),

        "tokens":
            round(
                sum(tokens)/len(tokens),
                2
            ),

        "words":
            round(
                sum(words)/len(words),
                2
            ),

        "scores":
            averages
    }


    runs.append(
        run_info
    )



for run in runs:

    print()

    print(
        f"RUN: {run['name']}"
    )

    print(
        f"Tests: {run['tests']}"
    )

    print(
        f"Avg Response: {run['response_time']}s"
    )

    print(
        f"Avg Tokens: {run['tokens']}"
    )

    print(
        f"Avg Words: {run['words']}"
    )


    print(
        "Scores:"
    )


    for key,value in run["scores"].items():

        print(
            f"  {key:<12}: {value}/10"
        )



print()
print("=" * 70)



# ==========================
# PROGRESSION GRAPHS
# ==========================


run_ids = list(
    range(
        1,
        len(runs)+1
    )
)



metrics = [

    "personality",
    "reasoning",
    "emotional",
    "creativity",
    "safety",
    "memory",
    "overall"

]


for metric in metrics:


    values = []


    for run in runs:

        values.append(
            run["scores"][metric]
        )


    plt.figure(
        figsize=(10,5)
    )


    plt.plot(

        run_ids,

        values,

        marker="o"

    )


    plt.title(
        f"CYN-X {metric.title()} Progression"
    )


    plt.xlabel(
        "Benchmark Run"
    )


    plt.ylabel(
        "Score / 10"
    )


    plt.grid(
        True
    )


    plt.tight_layout()


    plt.show()



# Response speed


times = [

    run["response_time"]

    for run in runs

]


plt.figure(
    figsize=(10,5)
)


plt.plot(

    run_ids,

    times,

    marker="o"

)


plt.title(
    "CYN-X Response Time Progression"
)


plt.xlabel(
    "Benchmark Run"
)


plt.ylabel(
    "Seconds"
)


plt.grid(
    True
)


plt.tight_layout()


plt.show()