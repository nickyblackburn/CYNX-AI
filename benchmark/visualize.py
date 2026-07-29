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


BASE = Path(
    "results"
)


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



                if isinstance(data, list):


                    for item in data:

                        add_result(
                            item,
                            file
                        )



                elif isinstance(data, dict):


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
        "No benchmark data found"
    )


    exit()






print(
    f"Loaded {len(results)} benchmark records"
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





    if "overall" not in scores:


        if scores:


            scores["overall"] = (

                sum(
                    scores.values()
                )
                /
                len(scores)

            )


        else:


            scores["overall"] = 0





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
        figsize=(8,4)
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



    categories[category].append(

        scores.get(

            "overall",

            0

        )

    )







    # ----------------------
    # FAILURE TRACKING
    # ----------------------


    if result.get(

        "failed",

        False

    ):


        failures.append(
            result
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


graph(

    "response_time",

    [

        x.get(

            "response_time_seconds",

            0

        )

        for x in results

    ],

    "Response Time",

    "Seconds"

)







graph(

    "tokens",

    [

        x.get(

            "estimated_tokens",

            0

        )

        for x in results

    ],

    "Token Usage",

    "Tokens"

)







graph(

    "words",

    [

        x.get(

            "response_words",

            0

        )

        for x in results

    ],

    "Response Length",

    "Words"

)







# ==========================
# FAILURE REPORT
# ==========================


with open(

    OUTPUT / "failures.json",

    "w",

    encoding="utf-8"

) as f:


    json.dump(

        failures,

        f,

        indent=2

    )





print(
    f"Failures: {len(failures)}"
)

# ==========================
# CREATE DASHBOARD
# ==========================


total_tests = len(results)



all_scores = [

    r.get(
        "scores",
        {}
    ).get(

        "overall",

        0

    )

    for r in results

]



average_score = (

    sum(all_scores) / len(all_scores)

    if all_scores

    else 0

)





average_response = (

    sum(

        r.get(
            "response_time_seconds",
            0
        )

        for r in results

    )

    /

    len(results)

    if results

    else 0

)





timestamp = datetime.now().strftime(

    "%Y-%m-%d %H:%M:%S"

)







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
repeat(4,1fr);

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

</div>




<div class="card">

<h3>
Failures
</h3>

<div class="stat">

{len(failures)}

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


</div>





<br>



<div class="grid">

"""





for image in graphs:


    html += f"""

<div class="card">


<h2>

{image.replace(".png","").replace("_"," ").title()}

</h2>



<img src="{image}">



</div>

"""





html += """

</div>



</body>


</html>

"""







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





webbrowser.open(

    dashboard.resolve().as_uri()

)