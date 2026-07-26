
# cyn_tester.py

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
    "latest_results.json"
)


# -----------------------------
# Prompt File Groups
# -----------------------------

GENERATOR_FILES = [
    "core.md",
    "personality.md",
    "habits.md",
    "character_motivation.md",
    "spontaneous.md",
    "modes.md"
]


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

            print("[LOADED]", path)


            with open(
                path,
                "r",
                encoding="utf-8"
            ) as file:

                system_prompt += (
                    "\n\n### "
                    + filename
                    + "\n\n"
                )

                system_prompt += file.read()


        else:

            print("[MISSING]", path)



    print(
        "\nPrompt stack loaded.\n"
    )


    return system_prompt



# -----------------------------
# Loading Animation
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
            f"\rCyn-X processing {frames[index % 4]} {elapsed}s"
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


    print("\n")
    print("=" * 60)
    print("USER PROMPT:")
    print(user_prompt)
    print("=" * 60)


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

            "num_ctx": 16384,

            "temperature": 0.8

        },

        "stream": True

    }



    output = ""


    stop_event = threading.Event()

    start_time = time.time()



    spinner = threading.Thread(
        target=loading_animation,
        args=(
            stop_event,
            start_time
        )
    )


    spinner.start()



    try:

        response = requests.post(
            OLLAMA,
            json=payload,
            stream=True,
            timeout=600
        )



        if response.status_code != 200:

            print("\nOLLAMA ERROR:")
            print(response.text)

            return ""



        print(
            "\n\nCYN-X OUTPUT:\n"
        )



        for line in response.iter_lines():

            if line:

                try:

                    data = json.loads(line)

                except Exception:

                    continue



                if "message" in data:

                    token = data["message"].get(
                        "content",
                        ""
                    )


                    print(
                        token,
                        end="",
                        flush=True
                    )


                    output += token



                if data.get("done"):

                    break



    except Exception as error:

        print("\nREQUEST ERROR:")
        print(error)



    finally:

        stop_event.set()

        spinner.join()



    elapsed = round(
        time.time() - start_time,
        2
    )


    print(
        f"\n\nFinished in {elapsed}s"
    )


    return output




# -----------------------------
# Generate Tests
# -----------------------------

def generate_tests():


    generator_system = load_cyn_personality(
        GENERATOR_FILES
    )


    prompt = """

Create test prompts for Cyn-X.

Test:

- personality consistency
- humor
- emotional responses
- technical questions
- memory behavior
- breaking character
- safety behavior
- randomness
- unusual situations
- mature topic handling

Only return JSON.

Format:

[
 {
  "category":"name",
  "prompt":"user message",
  "goal":"what this tests"
 }
]

"""


    print(
        "Generating tests..."
    )


    output = ask_model(
        prompt,
        generator_system
    )


    try:

        tests = json.loads(output)


    except Exception:

        print("\nJSON ERROR:")
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
            indent=4,
            ensure_ascii=False
        )


    print(
        f"Generated {len(tests)} tests"
    )


    return True




# -----------------------------
# Run Tests
# -----------------------------

def run_tests():


    if not os.path.exists(
        GENERATED_TEST_FILE
    ):

        print(
            "Missing generated_tests.json"
        )

        print(
            "Run generate_tests() first."
        )

        return



    test_system = load_cyn_personality(
        TEST_FILES
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



    results = []



    for number, test in enumerate(
        tests,
        1
    ):


        print(
            "\n"
            + "=" * 70
        )


        print(
            f"TEST {number}/{len(tests)}"
        )


        response = ask_model(
            test["prompt"],
            test_system
        )



        results.append({

            "test_number": number,

            "category": test["category"],

            "goal": test["goal"],

            "user_input": test["prompt"],

            "cyn_output": response,

            "timestamp": time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        })



        with open(
            RESULT_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                results,
                file,
                indent=4,
                ensure_ascii=False
            )



    print(
        "\nFinished!"
    )

    print(
        f"Completed {len(results)} tests."
    )

    print(
        "Saved:",
        os.path.abspath(
            RESULT_FILE
        )
    )




# -----------------------------
# Main
# -----------------------------

if __name__ == "__main__":


    print("==============================")
    print(" CYN-X AUTOMATIC TESTER")
    print("==============================")


    # Uncomment when you want new tests:
    #
    generate_tests()


    run_tests()