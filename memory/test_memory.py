from sqlite import connect
from memory import MemoryStore


conn = connect()

memory = MemoryStore(conn)


memory.add_memory(
    "preference",
    "User likes building CYN-X with Ollama."
)


memory.add_memory(
    "project",
    "CYN-X uses a ToolRouter system."
)


print(memory.retrieve_recent())