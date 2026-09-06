import json
import webbrowser

from pathlib import Path
from collections import defaultdict
from datetime import datetime


import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


# ==========================
# PATHS
# ==========================

# Resolve results relative to this dashboard.py file.
#
# This keeps the dashboard working when launched with:
#
# python -m benchmark.dashboard

BASE = Path(__file__).resolve().parent / "results"

RAW = BASE / "raw"

SECTIONS = BASE / "sections"

OUTPUT = BASE / "dashboard"


OUTPUT.mkdir(
    parents=True,
    exist_ok=True
)


# ==========================
# LOAD DATA
# ==========================

def load_results():

    results = []

    seen_ids = set()

    def add_result(data, source):

        if not isinstance(data, dict):

            return


        test_id = data.get(
            "test_id",
            data.get(
                "id",
                None
            )
        )


        if test_id:

            if test_id in seen_ids:

                return

            seen_ids.add(
                test_id
            )


        data["source_file"] = str(
            source
        )


        results.append(
            data
        )


    # ----------------------
    # RAW RESULTS
    # ----------------------

    if RAW.exists():

        for file in RAW.rglob("*.json"):

            try:

                with open(
                    file,
                    encoding="utf-8"
                ) as f:

                    data = json.load(f)


                if isinstance(
                    data,
                    list
                ):

                    for item in data:

                        add_result(
                            item,
                            file
                        )


                elif isinstance(
                    data,
                    dict
                ):

                    add_result(
                        data,
                        file
                    )


            except Exception as error:

                print(
                    "RAW LOAD ERROR:",
                    file,
                    error
                )


    # ----------------------
    # SECTION RESULTS
    # ----------------------

    if SECTIONS.exists():

        for file in SECTIONS.rglob("*.json"):

            try:

                with open(
                    file,
                    encoding="utf-8"
                ) as f:

                    data = json.load(f)


                if not isinstance(
                    data,
                    dict
                ):

                    continue


                parts = file.parts


                if "sections" in parts:

                    index = parts.index(
                        "sections"
                    )


                    if len(parts) > index + 1:

                        category = parts[
                            index + 1
                        ]

                    else:

                        category = "unknown"


                else:

                    category = "unknown"


                data["section"] = category


                add_result(
                    data,
                    file
                )


            except Exception as error:

                print(
                    "SECTION LOAD ERROR:",
                    file,
                    error
                )


    return results


results = load_results()


if not results:

    print(
        "No benchmark data found."
    )


    print(
        f"Checked RAW: {RAW.resolve()}"
    )


    print(
        f"Checked SECTIONS: {SECTIONS.resolve()}"
    )


    exit()


print(
    f"Loaded {len(results)} benchmark records"
)


# ==========================
# SCORE INTERPRETATION
# ==========================

def score_rating(score):

    if score is None:

        return "Not Scored"


    if score >= 3.0:

        return "Excellent"


    if score >= 2.0:

        return "Strong"


    if score >= 1.5:

        return "Good"


    if score >= 1.0:

        return "Developing"


    if score > 0:

        return "Needs Work"


    return "Needs Attention"


def human_category_name(name):

    if not name:

        return "Unknown"


    return (
        str(name)
        .replace("_", " ")
        .title()
    )


# ==========================
# NORMALIZE SCORES
# ==========================

for result in results:

    scores = result.get(
        "scores",
        {}
    )


    if not isinstance(
        scores,
        dict
    ):

        scores = {}

        result["scores"] = scores


    # Only calculate an overall score when
    # there are actual numeric component scores.
    #
    # Missing scores remain missing instead of
    # becoming a fake 0.00.

    if "overall" not in scores:

        numeric_scores = [

            value

            for value in scores.values()

            if isinstance(
                value,
                (int, float)
            )

        ]


        if numeric_scores:

            scores["overall"] = (

                sum(numeric_scores)

                /

                len(numeric_scores)

            )


print(
    "Scores normalized"
)


# ==========================
# GRAPH CREATOR
# ==========================

graphs = []


def graph(
    name,
    values,
    title,
    label
):

    if not values:

        return


    file = OUTPUT / f"{name}.png"


    plt.figure(
        figsize=(8, 4)
    )


    plt.plot(
        range(
            1,
            len(values) + 1
        ),
        values,
        marker="o"
    )


    plt.title(
        title
    )


    plt.ylabel(
        label
    )


    plt.xlabel(
        "Benchmark Test"
    )


    plt.grid(
        True
    )


    plt.tight_layout()


    plt.savefig(
        file,
        dpi=200
    )


    plt.close()


    graphs.append(
        file.name
    )


# ==========================
# PROCESS DATA
# ==========================

metrics = defaultdict(list)

categories = defaultdict(list)

test_ids = []

failures = []


for index, result in enumerate(results):

    scores = result.get(
        "scores",
        {}
    )


    if not isinstance(
        scores,
        dict
    ):

        scores = {}


    # ----------------------
    # METRICS
    # ----------------------

    result_metrics = result.get(
        "metrics",
        {}
    )


    if not isinstance(
        result_metrics,
        dict
    ):

        result_metrics = {}


    # ----------------------
    # TEST ID TRACKING
    # ----------------------

    test_id = result.get(
        "test_id",
        f"TEST-{index + 1}"
    )


    test_ids.append(
        test_id
    )


    # ----------------------
    # SCORE METRICS
    # ----------------------

    for key, value in scores.items():

        if isinstance(
            value,
            (int, float)
        ):

            metrics[key].append(
                value
            )


    # ----------------------
    # CATEGORY TRACKING
    # ----------------------

    category = result.get(
        "section",
        result.get(
            "category",
            "unknown"
        )
    )


    overall_score = scores.get(
        "overall",
        None
    )


    # Only put genuinely scored tests
    # into the category leaderboard.

    if isinstance(
        overall_score,
        (int, float)
    ):

        categories[category].append(
            overall_score
        )


    # ----------------------
    # FAILURE TRACKING
    # ----------------------

    runtime = result.get(
        "runtime",
        {}
    )


    if not isinstance(
        runtime,
        dict
    ):

        runtime = {}


    failed = result.get(
        "failed",
        runtime.get(
            "failed",
            False
        )
    )


    if failed:

        failures.append(
            result
        )


# ==========================
# CATEGORY LEADERBOARD DATA
# ==========================

leaderboard = []


for category, scores in categories.items():

    if scores:

        average = (

            sum(scores)

            /

            len(scores)

        )


        leaderboard.append(
            (
                category,
                average
            )
        )


leaderboard.sort(
    key=lambda x: x[1],
    reverse=True
)


# ==========================
# SCORE GRAPHS
# ==========================

for name, data in metrics.items():

    graph(
        name,
        data,
        f"CYN-X {name.title()}",
        "Score"
    )


# ==========================
# CATEGORY GRAPHS
# ==========================

for name, data in categories.items():

    graph(
        f"category_{name}",
        data,
        f"CYN-X {name.title()} Performance",
        "Score"
    )


# ==========================
# PERFORMANCE GRAPHS
# ==========================

# Response time is stored inside:
#
# result["metrics"]["response_time_seconds"]


graph(
    "response_time",
    [
        result.get(
            "metrics",
            {}
        ).get(
            "response_time_seconds",
            0
        )

        for result in results
    ],
    "Response Time",
    "Seconds"
)


# Token usage

graph(
    "tokens",
    [
        result.get(
            "metrics",
            {}
        ).get(
            "estimated_tokens",
            0
        )

        for result in results
    ],
    "Token Usage",
    "Tokens"
)


# Response length

graph(
    "words",
    [
        result.get(
            "metrics",
            {}
        ).get(
            "response_words",
            0
        )

        for result in results
    ],
    "Response Length",
    "Words"
)


# ==========================
# CREATE DASHBOARD
# ==========================

total_tests = len(results)


# Only include tests that actually
# have a numeric overall score.

all_scores = [

    result.get(
        "scores",
        {}
    ).get(
        "overall",
        None
    )

    for result in results

]


all_scores = [

    value

    for value in all_scores

    if isinstance(
        value,
        (int, float)
    )

]


average_score = (

    sum(all_scores)

    /

    len(all_scores)

    if all_scores

    else 0

)


# ==========================
# ERROR RATE
# ==========================

failure_count = len(
    failures
)


error_rate = (

    (
        failure_count
        /
        total_tests
    )
    *
    100

    if total_tests

    else 0

)


# ==========================
# FIXED AVERAGE RESPONSE TIME
# ==========================

response_times = [

    result.get(
        "metrics",
        {}
    ).get(
        "response_time_seconds",
        None
    )

    for result in results

]


# Only use valid numeric response times.

response_times = [

    value

    for value in response_times

    if isinstance(
        value,
        (int, float)
    )

]


average_response = (

    sum(response_times)

    /

    len(response_times)

    if response_times

    else 0

)


timestamp = datetime.now().strftime(
    "%Y-%m-%d %H:%M:%S"
)


# ==========================
# HTML
# ==========================

html = f"""

<html>

<head>

<title>

CYN-X Benchmark Dashboard

</title>


<style>

body {{

background:#07070f;

color:white;

font-family:Arial;

padding:20px;

}}


h1 {{

text-align:center;

color:#d8b4ff;

}}


.stats {{

display:grid;

grid-template-columns:

repeat(5,1fr);

gap:20px;

margin-bottom:30px;

}}


.card {{

background:#151525;

padding:20px;

border-radius:15px;

}}


.stat {{

font-size:30px;

font-weight:bold;

color:#c084fc;

}}


.rating {{

font-size:16px;

font-weight:bold;

margin-top:8px;

color:#d8b4ff;

}}


.grid {{

display:grid;

grid-template-columns:

repeat(2,1fr);

gap:20px;

}}


img {{

width:100%;

border-radius:10px;

}}


table {{

width:100%;

font-size:18px;

border-collapse:collapse;

}}


th, td {{

padding:12px;

border-bottom:1px solid #292940;

}}


th {{

color:#d8b4ff;

}}


.score {{

font-weight:bold;

color:#c084fc;

}}


</style>

</head>


<body>


<h1>

💜 CYN-X Benchmark Dashboard

</h1>


<div class="stats">


<div class="card">

<h3>

Total Tests

</h3>

<div class="stat">

{total_tests}

</div>

</div>


<div class="card">

<h3>

Average Score

</h3>

<div class="stat">

{average_score:.2f}

</div>

<div class="rating">

{score_rating(average_score)}

</div>

</div>


<div class="card">

<h3>

Failures

</h3>

<div class="stat">

{failure_count}

</div>

<div class="rating">

{"No Failures" if failure_count == 0 else "Failures Detected"}

</div>

</div>


<div class="card">

<h3>

Error Rate

</h3>

<div class="stat">

{error_rate:.1f}%

</div>

<div class="rating">

{"Excellent" if error_rate == 0 else "Needs Attention" if error_rate >= 10 else "Healthy"}

</div>

</div>


<div class="card">

<h3>

Avg Response

</h3>

<div class="stat">

{average_response:.2f}s

</div>

</div>


</div>


"""


# ==========================
# CATEGORY LEADERBOARD CARD
# ==========================

html += """

<div class="card">

<h2>

🏆 Category Leaderboard

</h2>


<table>


<tr>

<th align="left">

Rank

</th>


<th align="left">

Category

</th>


<th align="left">

Average Score

</th>


<th align="left">

Assessment

</th>

</tr>

"""


for rank, (category, score) in enumerate(

    leaderboard,

    start=1

):

    rating = score_rating(
        score
    )


    display_category = human_category_name(
        category
    )


    html += f"""

<tr>

<td>

#{rank}

</td>


<td>

{display_category}

</td>


<td class="score">

{score:.2f}

</td>


<td>

{rating}

</td>

</tr>

"""


html += f"""

</table>

</div>


<br>


<div class="card">

<h3>

Benchmark Run

</h3>


<p>

Generated:

{timestamp}

</p>


<p>

Tests tracked:

{len(test_ids)}

</p>


<p>

Tests with scores:

{len(all_scores)}

</p>


<p>

Failures:

{failure_count}

</p>


<p>

Error Rate:

{error_rate:.2f}%

</p>


<p>

Average Response Time:

{average_response:.2f}s

</p>


</div>


<br>


<div class="grid">

"""


for image in graphs:

    html += f"""

<div class="card">

<h2>

{image.replace(".png", "").replace("_", " ").title()}

</h2>


<img src="{image}">


</div>

"""


html += """

</div>


</body>

</html>

"""


# ==========================
# SAVE DASHBOARD
# ==========================

dashboard = OUTPUT / "index.html"


dashboard.write_text(
    html,
    encoding="utf-8"
)


print()


print(
    "Dashboard created:"
)


print(
    dashboard
)


print(
    f"Total tests: {total_tests}"
)


print(
    f"Failures: {failure_count}"
)


print(
    f"Error rate: {error_rate:.2f}%"
)


print(
    f"Average score: {average_score:.2f}"
)


print(
    f"Average response time: {average_response:.2f}s"
)


webbrowser.open(
    dashboard.resolve().as_uri()
)