class ContextManager:


    def __init__(
        self,
        memory_store,
        knowledge_store
    ):

        self.memory_store = memory_store
        self.knowledge_store = knowledge_store



    def build_context(
        self,
        user_message
    ):

        context = []


        # Always load tiny identity
        context.append(
            self.get_identity()
        )


        # Retrieve memories
        memories = self.memory_store.search(
            user_message,
            limit=3
        )


        if memories:

            context.append(
                "RELEVANT MEMORY:\n"
                + "\n".join(memories)
            )



        # Retrieve docs
        docs = self.knowledge_store.search(
            user_message,
            limit=2
        )


        if docs:

            context.append(
                "RELEVANT DOCUMENTS:\n"
                + "\n".join(docs)
            )



        return "\n\n".join(context)



    def get_identity(self):

        return """
You are CYN-X.

Personality:
- playful
- curious
- analytical
- glitchy

Be helpful and consistent.
"""