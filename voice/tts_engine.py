import subprocess


class TTSEngine:

    def __init__(self):

        self.model = (
            "voice/models/en_US-lessac-medium.onnx"
        )


    def generate(
        self,
        text,
        output="cyn_output.wav"
    ):

        command = [
            "piper",
            "--model",
            self.model,
            "--output_file",
            output
        ]

        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            text=True
        )

        process.communicate(text)

        return output