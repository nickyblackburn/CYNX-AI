import pygame
import time


class AudioPlayer:

    def __init__(self):
        pygame.mixer.init()

    def play(self, filepath):
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            time.sleep(0.1)