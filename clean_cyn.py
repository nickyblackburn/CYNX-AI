from pathlib import Path

PROMPT_DIR = Path("prompts_new")

# Things that make Cyn sound like a report generator
REMOVE_LINES = [
    "Analysis:",
    "Recommendation:",
    "Observation:",
    "Updating database:",
    "Human behavior analysis",
    "Human response detected",
    "I'm detecting...",
    "This could be...",
    "Please keep in mind...",
    "Recommendation: begin conversation sequence.",
]

BACKUP_DIR = Path("prompts_backup")


def clean_file(path: Path):
    text = path.read_text(encoding="utf-8")

    original = text

    lines = text.splitlines()

    cleaned = []

    for line in lines:
        skip = False

        for bad in REMOVE_LINES:
            if bad.lower() in line.lower():
                skip = True
                break

        if not skip:
            cleaned.append(line)

    new_text = "\n".join(cleaned)

    if new_text != original:
        print(f"Cleaned: {path}")
        path.write_text(new_text, encoding="utf-8")


def main():
    if not PROMPT_DIR.exists():
        print("prompts_new folder not found")
        return

    # backup first
    import shutil

    if not BACKUP_DIR.exists():
        shutil.copytree(PROMPT_DIR, BACKUP_DIR)
        print("Backup created:", BACKUP_DIR)

    for file in PROMPT_DIR.rglob("*.md"):
        clean_file(file)

    print("Done cleaning Cyn prompt files.")


if __name__ == "__main__":
    main()