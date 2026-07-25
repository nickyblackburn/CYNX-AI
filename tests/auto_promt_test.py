import json
import requests
import threading
import time
import sys
import os


MODEL = "cyn-x"
OLLAMA = "http://localhost:11434/api/chat"


# Files
PROMPTS_FOLDER = "../prompts"

GENERATED_TEST_FILE = "generated_tests.json"

RESULT_FOLDER = "results"
RESULT_FILE = os.path.join(
    RESULT_FOLDER,
    "cyn_conversation_log.txt"
)


CYN_FILES = [
    "core.md",
    "personality.md",
    "habits.md",
    "modes.md",
    "safety.md",
    "examples.md"
]


# --------------------------------
# Load Cyn-X Personality
# --------------------------------

def load_cyn_personality():

    print("\nLoading Cyn-X personality files...\n")

    system_prompt = ""


    for filename in CYN_FILES:

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
        "\nPersonality loaded.\n"
    )

    return system_prompt



# --------------------------------
# Spinner
# --------------------------------

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



# --------------------------------
# Ollama Request
# --------------------------------

def ask_model(user_prompt, system_prompt):

    response_data = {}


    def request():

        try:

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

                "stream": False
            }


            response = requests.post(
                OLLAMA,
                json=payload,
                timeout=600
            )


            response_data["json"] = response.json()


        except Exception as error:

            response_data["error"] = str(error)



    stop_event = threading.Event()

    start_time = time.time()



    thread = threading.Thread(
        target=request
    )

    thread.start()



    spinner = threading.Thread(
        target=loading_animation,
        args=(
            stop_event,
            start_time
        )
    )

    spinner.start()



    thread.join()


    stop_event.set()

    spinner.join()



    if "error" in response_data:

        return (
            "ERROR:\n"
            + response_data["error"]
        )


    data = response_data["json"]


    if "message" not in data:

        return (
            "OLLAMA ERROR:\n"
            + str(data)
        )


    return data["message"]["content"]




# --------------------------------
# Generate Tests
# --------------------------------

def generate_tests(system_prompt):


    print(
        "Generating Cyn-X test prompts..."
    )


    prompt = """

Create 10 test prompts for Cyn-X.

Test categories:

- personality consistency
- humor
- emotional responses
- technical knowledge
- memory behavior
- breaking character
- safety behavior
- randomness
- strange human situations
- mature topic handling


The prompts should test how Cyn reacts.

Do not answer the prompts.

Return JSON only.

Format:

[
 {
  "category": "name",
  "prompt": "user message",
  "goal": "what this tests"
 }
]

"""


    output = ask_model(
        prompt,
        system_prompt
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




# --------------------------------
# Run Tests
# --------------------------------

def run_tests(system_prompt):


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
                f"Test {number}/{len(tests)}:"
                ,
                test["category"]
            )


            user_message = test["prompt"]


            response = ask_model(
                user_message,
                system_prompt
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
            )

            log.write(
                test["category"]
                +
                "\n\n"
            )


            log.write(
                "GOAL:\n"
            )

            log.write(
                test["goal"]
                +
                "\n\n"
            )


            log.write(
                "USER:\n"
            )

            log.write(
                user_message
                +
                "\n\n"
            )


            log.write(
                "CYN-X OUTPUT:\n"
            )

            log.write(
                response
                +
                "\n"
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




# --------------------------------
# Main
# --------------------------------

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


    cyn_system = load_cyn_personality()


    if generate_tests(cyn_system):

        run_tests(cyn_system)