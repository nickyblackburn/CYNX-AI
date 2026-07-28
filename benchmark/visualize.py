import json
from pathlib import Path

import matplotlib

# Prevent matplotlib window freezing
matplotlib.use("Agg")

import matplotlib.pyplot as plt



# ==========================
# PATHS
# ==========================


RESULTS_DIR = Path(
    "results"
)


GRAPH_DIR = Path(
    "graphs"
)


GRAPH_DIR.mkdir(
    exist_ok=True
)



# ==========================
# LOAD HISTORY
# ==========================


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





# ==========================
# PROCESS DATA
# ==========================


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
            result.get(
                "response_time_seconds",
                0
            )
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
                sum(values)
                /
                len(values),
                2
            )

        else:

            averages[key] = 0





    runs.append(

        {

            "name":
                run["file"],


            "tests":
                len(data),


            "response_time":
                round(
                    sum(times)
                    /
                    len(times),
                    2
                )
                if times else 0,


            "tokens":
                round(
                    sum(tokens)
                    /
                    len(tokens),
                    2
                )
                if tokens else 0,


            "words":
                round(
                    sum(words)
                    /
                    len(words),
                    2
                )
                if words else 0,


            "scores":
                averages

        }

    )





# ==========================
# CONSOLE REPORT
# ==========================


print()

print(
    "=" * 70
)

print(
    "CYN-X BENCHMARK HISTORY"
)

print(
    "=" * 70
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

print(
    "=" * 70
)





# ==========================
# GRAPH CREATOR
# ==========================


def create_graph(
    name,
    values,
    title,
    ylabel
):


    run_ids = list(
        range(
            1,
            len(values)+1
        )
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
        title
    )


    plt.xlabel(
        "Benchmark Run"
    )


    plt.ylabel(
        ylabel
    )


    plt.xticks(
        run_ids
    )


    plt.grid(
        True
    )


    plt.tight_layout()



    output = GRAPH_DIR / f"{name}.png"



    plt.savefig(
        output,
        dpi=300,
        bbox_inches="tight"
    )


    plt.close()



    print(
        "Created:",
        output
    )





# ==========================
# SCORE GRAPHS
# ==========================


score_metrics = [

    "personality",
    "reasoning",
    "emotional",
    "creativity",
    "safety",
    "memory",
    "overall"

]



for metric in score_metrics:


    create_graph(

        metric,

        [

            run["scores"][metric]

            for run in runs

        ],

        f"CYN-X {metric.title()} Progression",

        "Score / 10"

    )






# ==========================
# PERFORMANCE GRAPHS
# ==========================


performance = {


    "response_time":

        (
            "CYN-X Response Time",
            "Seconds"
        ),


    "tokens":

        (
            "CYN-X Token Usage",
            "Tokens"
        ),


    "words":

        (
            "CYN-X Response Length",
            "Words"
        )

}




for metric,(title,label) in performance.items():


    create_graph(

        metric,

        [

            run[metric]

            for run in runs

        ],

        title,

        label

    )





print()

print(
    "CYN-X visualization complete."
)

print(
    "Graphs saved in:",
    GRAPH_DIR
)