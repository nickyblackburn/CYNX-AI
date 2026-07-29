class ContextManager:




    def __init__(
        self,
        memory_store,
        knowledge_store
    ):

        self.memory_store = memory_store
        self.knowledge_store = knowledge_store


        print("===== CONTEXT INIT =====")
        print("MEMORY:", type(memory_store))
        print("KNOWLEDGE:", type(knowledge_store))
        print("========================")


    
    def build_context(
        self,
        user_id,
        user_message
    ):

        memory_context = ""
        knowledge_context = ""


        # MEMORY

        try:

            memories = self.memory_store.search(
                user_id,
                user_message,
                limit=5
            )


            if memories:

                memory_context = "\n".join(memories)


            print("[MEMORY FOUND]")
            print(memory_context)


        except Exception as e:

            print(
                "[MEMORY ERROR]",
                e
            )



        # KNOWLEDGE

        try:

            documents = self.knowledge_store.search(
                user_message,
                limit=3
            )


            if documents:

                knowledge_context = "\n".join(
                    documents
                )


        except Exception as e:

            print(
                "[KNOWLEDGE ERROR]",
                e
            )



        return {

            "memory": memory_context,

            "knowledge": knowledge_context

        }