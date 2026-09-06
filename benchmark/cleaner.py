
"""
CYN-X Benchmark Cleanup Tool

Purpose:
    Remove generated benchmark artifacts while preserving:

        benchmark/suites/**/*.json
        dashboard image files
        source code
        benchmark configuration

SAFE BY DEFAULT:
    Without --execute, this only shows what would be deleted.

Examples:

    Preview cleanup:
        python benchmark/cleanup.py

    Actually clean:
        python benchmark/cleanup.py --execute

    Include temporary development files:
        python benchmark/cleanup.py --execute --temp

"""

from __future__ import annotations

import argparse
from pathlib import Path


# =====================================
# Project Paths
# =====================================

PROJECT_ROOT = Path(".")

BENCHMARK_DIR = PROJECT_ROOT / "benchmark"

SUITES_DIR = BENCHMARK_DIR / "suites"

RESULTS_DIR = BENCHMARK_DIR / "results"

# Change this if your dashboard has a different location.
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"


# =====================================
# Files That Must NEVER Be Deleted
# =====================================

PROTECTED_EXTENSIONS = {
    ".py",
    ".pyw",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".env",
}

DASHBOARD_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".svg",
}


# =====================================
# Temporary Development Files
# =====================================

TEMP_FILES = {
    "run_storage_test.py",
}

TEMP_EXTENSIONS = {
    ".tmp",
    ".temp",
    ".bak",
    ".old",
    ".swp",
}


# =====================================
# Cleanup Manager
# =====================================

class BenchmarkCleaner:

    def __init__(
        self,
        execute: bool = False,
        remove_temp: bool = False,
    ):

        self.execute = execute
        self.remove_temp = remove_temp

        self.deleted = []
        self.kept = []
        self.errors = []

    # =================================
    # Display Action
    # =================================

    def show_delete(self, path: Path):

        if self.execute:

            print(
                f"[DELETE] {path}"
            )

            try:

                path.unlink()

                self.deleted.append(path)

            except Exception as error:

                self.errors.append(
                    f"{path}: {error}"
                )

                print(
                    f"[ERROR] {path}: {error}"
                )

        else:

            print(
                f"[DRY-RUN] Would delete: {path}"
            )

    # =================================
    # Check Protected File
    # =================================

    def is_protected(
        self,
        path: Path
    ) -> bool:

        # ---------------------------------
        # Never delete source/config files
        # ---------------------------------

        if path.suffix.lower() in PROTECTED_EXTENSIONS:

            return True

        # ---------------------------------
        # NEVER delete benchmark questions
        # ---------------------------------

        try:

            path.relative_to(
                SUITES_DIR
            )

            # Everything inside suites is protected.
            #
            # This means your JSON questions,
            # metadata, images, etc. remain safe.

            return True

        except ValueError:

            pass

        # ---------------------------------
        # Protect dashboard images
        # ---------------------------------

        try:

            path.relative_to(
                DASHBOARD_DIR
            )

            if path.suffix.lower() in (
                DASHBOARD_IMAGE_EXTENSIONS
            ):

                return True

        except ValueError:

            pass

        return False

    # =================================
    # Clean Benchmark Results
    # =================================

    def clean_results(self):

        print()
        print("=" * 60)
        print("CLEANING GENERATED BENCHMARK RESULTS")
        print("=" * 60)

        if not RESULTS_DIR.exists():

            print(
                "No benchmark results directory found."
            )

            return

        # Delete files first.
        #
        # This includes generated JSON result files,
        # logs, summaries, temporary files, etc.
        #
        # The benchmark input JSON files are NOT here;
        # those live under benchmark/suites/.

        for path in RESULTS_DIR.rglob("*"):

            if not path.is_file():

                continue

            if self.is_protected(path):

                self.kept.append(path)

                print(
                    f"[KEEP] {path}"
                )

                continue

            self.show_delete(path)

    # =================================
    # Clean Temporary Development Files
    # =================================

    def clean_temp_files(self):

        if not self.remove_temp:

            return

        print()
        print("=" * 60)
        print("CLEANING TEMPORARY DEVELOPMENT FILES")
        print("=" * 60)

        # Known temporary helper
        for filename in TEMP_FILES:

            path = PROJECT_ROOT / filename

            if path.exists() and path.is_file():

                self.show_delete(path)

        # Temporary files throughout project
        for path in PROJECT_ROOT.rglob("*"):

            if not path.is_file():

                continue

            # Don't scan virtual environments or git internals.
            parts = set(path.parts)

            if (
                ".git" in parts
                or ".venv" in parts
                or "venv" in parts
                or "__pycache__" in parts
            ):

                continue

            if path.suffix.lower() in TEMP_EXTENSIONS:

                if not self.is_protected(path):

                    self.show_delete(path)

    # =================================
    # Remove Empty Result Directories
    # =================================

    def clean_empty_directories(self):

        print()
        print("=" * 60)
        print("REMOVING EMPTY RESULT DIRECTORIES")
        print("=" * 60)

        if not RESULTS_DIR.exists():

            return

        # Deepest directories first
        directories = sorted(
            [
                p
                for p in RESULTS_DIR.rglob("*")
                if p.is_dir()
            ],
            key=lambda p: len(p.parts),
            reverse=True
        )

        for directory in directories:

            try:

                if not any(directory.iterdir()):

                    if self.execute:

                        print(
                            f"[DELETE DIR] {directory}"
                        )

                        directory.rmdir()

                        self.deleted.append(
                            directory
                        )

                    else:

                        print(
                            f"[DRY-RUN] Would delete empty "
                            f"directory: {directory}"
                        )

            except Exception as error:

                self.errors.append(
                    f"{directory}: {error}"
                )

    # =================================
    # Safety Report
    # =================================

    def print_protected_info(self):

        print()
        print("=" * 60)
        print("PROTECTED FILES")
        print("=" * 60)

        print(
            f"Question directory: {SUITES_DIR}"
        )

        print(
            "All files under benchmark/suites/ "
            "are protected."
        )

        print(
            f"Dashboard: {DASHBOARD_DIR}"
        )

        print(
            "Dashboard image files are protected."
        )

        print(
            "Python/source/config files are protected."
        )

    # =================================
    # Summary
    # =================================

    def summary(self):

        print()
        print("=" * 60)
        print("CLEANUP COMPLETE")
        print("=" * 60)

        if self.execute:

            print(
                f"Files/directories deleted: "
                f"{len(self.deleted)}"
            )

        else:

            print(
                "DRY-RUN COMPLETE"
            )

            print(
                "Nothing was deleted."
            )

            print()
            print(
                "Run again with --execute "
                "to perform the cleanup."
            )

        if self.kept:

            print(
                f"Protected files encountered: "
                f"{len(self.kept)}"
            )

        if self.errors:

            print()
            print(
                "Errors:"
            )

            for error in self.errors:

                print(
                    f"  {error}"
                )


# =====================================
# Main
# =====================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Clean generated CYN-X benchmark "
            "files while protecting benchmark "
            "questions and dashboard images."
        )
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually delete files. "
            "Without this flag, only preview."
        )
    )

    parser.add_argument(
        "--temp",
        action="store_true",
        help=(
            "Also remove temporary development "
            "files such as run_storage_test.py."
        )
    )

    args = parser.parse_args()

    print()
    print("=" * 60)
    print("CYN-X BENCHMARK CLEANUP")
    print("=" * 60)

    print(
        f"Mode: "
        f"{'EXECUTE' if args.execute else 'DRY-RUN'}"
    )

    cleaner = BenchmarkCleaner(
        execute=args.execute,
        remove_temp=args.temp,
    )

    cleaner.print_protected_info()

    cleaner.clean_results()

    cleaner.clean_temp_files()

    cleaner.clean_empty_directories()

    cleaner.summary()


# =====================================
# Entry Point
# =====================================

if __name__ == "__main__":

    main()

