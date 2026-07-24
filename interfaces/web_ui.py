"""
Web UI adapter placeholder for future HTTP/websocket front-end.
"""

class WebUIAdapter:
    def __init__(self, chat_engine, logger=None):
        self.chat_engine = chat_engine
        self.logger = logger

    def start(self, host='127.0.0.1', port=8000):
        raise NotImplementedError("Web UI adapter not implemented in scaffold")
