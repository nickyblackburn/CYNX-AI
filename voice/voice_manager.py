class VoiceManager:

    def __init__(self, tts_engine, audio_player):
        self.tts = tts_engine
        self.player = audio_player


    def speak(self, text):

        audio_file = self.tts.generate(text)

        self.player.play(audio_file)