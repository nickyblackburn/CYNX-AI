
import sys


def get_benchmark_command():
    """
    Parse benchmark command-line arguments.

    Supported:

        python -m benchmark.runner
        python -m benchmark.runner quick
        python -m benchmark.runner normal
        python -m benchmark.runner full

        python -m benchmark.runner --all

        python -m benchmark.runner --suite personality

        python -m benchmark.runner --suite personality safety memory

        python -m benchmark.runner --suite personality --limit 5

        python -m benchmark.runner --all --limit 10
    """

    args = sys.argv[1:]

    # ---------------------------------
    # No arguments
    # ---------------------------------

    if not args:
        return {
            "mode": "all",
            "suites": None,
            "limit": None
        }

    # ---------------------------------
    # Help
    # ---------------------------------

    if args[0] in (
        "--help",
        "-h",
        "--elp"
    ):

        print()
        print("=" * 60)
        print("CYN-X BENCHMARK")
        print("=" * 60)
        print()
        print("Usage:")
        print()
        print("  python -m benchmark.runner --all")
        print("      Run every benchmark suite.")
        print()
        print("  python -m benchmark.runner --suite NAME")
        print("      Run one benchmark suite.")
        print()
        print("  python -m benchmark.runner --suite NAME NAME")
        print("      Run multiple benchmark suites.")
        print()
        print("  python -m benchmark.runner --suite NAME --limit N")
        print("      Run selected suite(s) with a test limit.")
        print()
        print("  python -m benchmark.runner --all --limit N")
        print("      Run all suites with a test limit.")
        print()
        print("Legacy modes:")
        print()
        print("  quick")
        print("  normal")
        print("  full")
        print()
        print("=" * 60)
        print()

        return {
            "mode": "help",
            "suites": None,
            "limit": None
        }

    # ---------------------------------
    # Defaults
    # ---------------------------------

    mode = "all"
    suites = None
    limit = None

    i = 0

    # ---------------------------------
    # Parse arguments
    # ---------------------------------

    while i < len(args):

        argument = args[i].lower()

        # -----------------------------
        # --all
        # -----------------------------

        if argument in (
            "--all",
            "all"
        ):

            mode = "all"
            i += 1
            continue

        # -----------------------------
        # --suite
        # -----------------------------

        if argument in (
            "--suite",
            "-s"
        ):

            mode = "suite"

            suites = []

            i += 1

            # Collect suite names until
            # another option appears.

            while i < len(args):

                suite_name = args[i]

                if suite_name.startswith("-"):
                    break

                suites.append(
                    suite_name
                )

                i += 1

            if not suites:

                print()
                print(
                    "ERROR: --suite requires "
                    "at least one suite name."
                )
                print()

                return {
                    "mode": "error",
                    "suites": None,
                    "limit": None
                }

            continue

        # -----------------------------
        # --limit
        # -----------------------------

        if argument in (
            "--limit",
            "-l"
        ):

            i += 1

            if i >= len(args):

                print()
                print(
                    "ERROR: --limit requires "
                    "a number."
                )
                print()

                return {
                    "mode": "error",
                    "suites": suites,
                    "limit": None
                }

            try:

                limit = int(
                    args[i]
                )

                if limit < 1:
                    raise ValueError

            except ValueError:

                print()
                print(
                    "ERROR: --limit must be "
                    "a positive integer."
                )
                print()

                return {
                    "mode": "error",
                    "suites": suites,
                    "limit": None
                }

            i += 1
            continue

        # -----------------------------
        # Legacy benchmark modes
        # -----------------------------

        if argument in (
            "quick",
            "normal",
            "full"
        ):

            mode = argument
            i += 1
            continue

        # -----------------------------
        # Unknown argument
        # -----------------------------

        print()
        print(
            f"ERROR: Unknown benchmark option: "
            f"{args[i]}"
        )
        print()
        print(
            "Use --help for available commands."
        )
        print()

        return {
            "mode": "error",
            "suites": suites,
            "limit": limit
        }

    # ---------------------------------
    # Return parsed command
    # ---------------------------------

    return {
        "mode": mode,
        "suites": suites,
        "limit": limit
    }
