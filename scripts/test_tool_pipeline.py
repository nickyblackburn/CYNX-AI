import sys
sys.path.insert(0, r'C:\Users\nickk\Documents\CYNX-AI')
import interfaces.web.app as app
engine = app.chat_engine

tests=[
    "how many smoking sessions do I have?",
    "what was my last smoking session?",
    "show my recent smoking sessions",
    "log one cigarette",
    "log one weed hit",
    "show my smoking stats",
    "reset my smoke counter",
    "find target vibrator"
]
for t in tests:
    print('\n[USER]', t)
    resp = engine.handle_user_message(user_id='test', text=t)
    print('[CYN]', resp)
