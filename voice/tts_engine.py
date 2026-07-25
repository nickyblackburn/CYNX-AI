class VoiceEngine:

    def __init__(self, tts):
        self.tts = tts


    def speak(self, text):

        self.tts.generate(
            text,
            output="cyn_output.wav"
        )