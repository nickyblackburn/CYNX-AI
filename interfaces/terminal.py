"""
Terminal adapter: simple REPL loop that uses ChatEngine to process messages.
"""
import sys
from typing import Optional


class TerminalAdapter:
    def __init__(self, chat_engine, logger=None):
        self.chat_engine = chat_engine
        self.logger = logger

    def run(self):
        print("Welcome to CYN-X (terminal). Type /exit to quit. Use /mode <name> to change mode.")
        mode = 'normal'
        while True:
            try:
                text = input('You: ')
            except EOFError:
                print('\nGoodbye')
                return
            if not text:
                continue
            if text.strip() == '/exit':
                print('Bye')
                return
            if text.startswith('/mode '):
                mode = text.split('/mode ', 1)[1].strip() or 'normal'
                print(f'Mode set to {mode}')
                continue
            resp = self.chat_engine.handle_user_message(user_id='terminal', text=text, mode=mode)
            print('\nCYN-X:', resp, '\n')
