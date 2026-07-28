import sys


def get_benchmark_command():

    if len(sys.argv) < 2:

        return "normal"


    command = sys.argv[1].lower()


    valid = [

        "quick",
        "normal",
        "full"

    ]


    if command in valid:

        return command


    # category mode

    return command