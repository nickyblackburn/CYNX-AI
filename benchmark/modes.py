# benchmark/modes.py

from typing import Optional


def apply_benchmark_filters(
    tests: list[dict],
    limit: Optional[int] = None,
    categories: Optional[list[str]] = None,
    suites: Optional[list[str]] = None,
) -> list[dict]:
    """
    Filters benchmark tests before execution.

    Args:
        tests:
            Loaded benchmark test list.

        limit:
            Maximum number of tests to run.

        categories:
            Only run tests matching these categories.

        suites:
            Only run tests from these benchmark suites.

    Returns:
        Filtered list of benchmark tests.
    """


    filtered = tests.copy()



    # -------------------------------
    # Category filtering
    # -------------------------------

    if categories:

        filtered = [

            test

            for test in filtered

            if test.get("category")

            in categories

        ]



    # -------------------------------
    # Suite filtering
    # -------------------------------

    if suites:

        filtered = [

            test

            for test in filtered

            if test.get("suite")

            in suites

        ]



    # -------------------------------
    # Test limit
    # -------------------------------

    if limit:

        filtered = filtered[:limit]



    return filtered





def get_benchmark_mode(
    mode: str
) -> dict:
    """
    Returns preset benchmark configurations.

    Modes:
        quick
        normal
        full
    """


    modes = {


        "quick": {

            "limit": 5,

            "categories": None,

            "suites": None

        },


        "normal": {

            "limit": 15,

            "categories": None,

            "suites": None

        },


        "full": {

            "limit": None,

            "categories": None,

            "suites": None

        }

    }



    return modes.get(

        mode.lower(),

        modes["normal"]

    )