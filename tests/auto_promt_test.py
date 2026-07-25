import json
import requests
import threading
import time
import sys
import os


MODEL = "cyn-x"
OLLAMA = "http://localhost:11434/api/chat"


# -----------------------------
# Paths
# -----------------------------

PROMPTS_FOLDER = "../prompts"

GENERATED_TEST_FILE = "generated_tests.json"

RESULT_FOLDER = "results"

RESULT_FILE = os.path.join(
    RESULT_FOLDER,
    "cyn_conversation_log.txt"
)



# -----------------------------
# Prompt File Groups
# -----------------------------

# Used when creating test questions
GENERATOR_FILES = [
    "core.md",
    "personality.md",
    "habits.md",
    "character_motivation.md",
    "spontaneous.md",
    "modes.md"
]


# Used when testing Cyn responses
TEST_FILES = [
    "core.md",
    "personality.md",
    "habits.md",
    "character_motivation.md",
    "spontaneous.md",
    "modes.md",
    "safety.md",
    "examples.md"
]



# -----------------------------
# Load Prompt Files
# -----------------------------

def load_cyn_personality(files):

    print("\nLoading Cyn-X files...\n")

    system_prompt = ""


    for filename in files:

        path = os.path.join(
            PROMPTS_FOLDER,
            filename
        )


        if os.path.exists(path):

            print(
                "[LOADED]",
                path
            )


            with open(
                path,
                "r",
                encoding="utf-8"
            ) as file:

                system_prompt += (
                    "\n\n"
                    "### "
                    + filename
                    + "\n\n"
                )

                system_prompt += file.read()


        else:

            print(
                "[MISSING]",
                path
            )


    print(
        "\nPrompt stack loaded.\n"
    )

    return system_prompt




# -----------------------------
# Spinner
# -----------------------------

def loading_animation(stop_event, start_time):

    frames = [
        "|",
        "/",
        "-",
        "\\"
    ]

    index = 0


    while not stop_event.is_set():

        elapsed = round(
            time.time() - start_time,
            1
        )


        sys.stdout.write(
            f"\rCyn-X thinking {frames[index % len(frames)]} {elapsed}s"
        )

        sys.stdout.flush()


        index += 1

        time.sleep(0.2)



    sys.stdout.write(
        "\r" + " " * 60 + "\r"
    )





# -----------------------------
# Ollama Request
# -----------------------------

def ask_model(user_prompt, system_prompt):

    payload = {

        "model": MODEL,

        "messages": [

            {
                "role": "system",
                "content": system_prompt
            },

            {
                "role": "user",
                "content": user_prompt
            }

        ],

        "options": {
            "num_ctx": 16384
        },

        "stream": True
    }


    response = requests.post(
        OLLAMA,
        json=payload,
        stream=True,
        timeout=600
    )


    output = ""


    for line in response.iter_lines():

        if line:

            data = json.loads(line)

            if "message" in data:

                token = data["message"]["content"]

                print(
                    token,
                    end="",
                    flush=True
                )

                output += token


    print("\n")

    return output
# -----------------------------
# Generate Tests
# -----------------------------

def generate_tests():


    generator_system = load_cyn_personality(
        GENERATOR_FILES
    )


    print(
        "Generating Cyn-X test prompts..."
    )


    prompt = """

Create 3 test prompts for Cyn-X.

Generate realistic user messages that test:

- personality consistency
- humor
- emotional reactions
- technical questions
- memory behavior
- breaking character
- safety behavior
- randomness
- unusual situations
- mature topic handling


Only create the USER messages.

Do not answer them.

Return JSON only.

Format:

[
 {
  "category":"category name",
  "prompt":"user message",
  "goal":"what this tests"
 }
]

"""


    output = ask_model(
        prompt,
        generator_system
    )


    try:

        tests = json.loads(output)


    except Exception:

        print(
            "\nJSON ERROR:"
        )

        print(output)

        return False



    with open(
        GENERATED_TEST_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            tests,
            file,
            indent=4
        )


    print(
        "\nGenerated",
        len(tests),
        "tests."
    )


    return True





# -----------------------------
# Run Tests
# -----------------------------

def run_tests():


    test_system = load_cyn_personality(
        TEST_FILES
    )


    print(
        "\nRunning Cyn-X tests...\n"
    )


    os.makedirs(
        RESULT_FOLDER,
        exist_ok=True
    )


    with open(
        GENERATED_TEST_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        tests = json.load(file)




    with open(
        RESULT_FILE,
        "w",
        encoding="utf-8"
    ) as log:


        for number, test in enumerate(tests, 1):


            print(
                f"Test {number}/{len(tests)}:",
                test["category"]
            )


            user_message = test["prompt"]


            response = ask_model(
                user_message,
                test_system
            )



            log.write(
                "\n"
                + "=" * 70
                + "\n"
            )


            log.write(
                f"TEST {number}\n\n"
            )


            log.write(
                "CATEGORY:\n"
                + test["category"]
                + "\n\n"
            )


            log.write(
                "GOAL:\n"
                + test["goal"]
                + "\n\n"
            )


            log.write(
                "USER:\n"
                + user_message
                + "\n\n"
            )


            log.write(
                "CYN-X OUTPUT:\n"
                + response
                + "\n"
            )



    print(
        "\nFinished!"
    )

    print(
        "Saved:"
    )

    print(
        os.path.abspath(
            RESULT_FILE
        )
    )






# -----------------------------
# Main
# -----------------------------

if __name__ == "__main__":


    print(
        "=============================="
    )

    print(
        " CYN-X AUTOMATIC TESTER"
    )

    print(
        "=============================="
    )


    if generate_tests():

        run_tests()