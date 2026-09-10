


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

                # MemoryManager.search() may return
                # formatted strings or memory records.

                if isinstance(memories, str):

                    memory_context = memories

                else:

                    formatted_memories = []

                    for memory in memories:

                        if isinstance(memory, str):

                            formatted_memories.append(
                                memory
                            )

                        elif isinstance(memory, dict):

                            content = memory.get(
                                "content",
                                ""
                            )

                            if content:

                                formatted_memories.append(
                                    content
                                )

                        else:

                            formatted_memories.append(
                                str(memory)
                            )


                    memory_context = "\n".join(
                        formatted_memories
                    )


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

                if isinstance(documents, str):

                    knowledge_context = documents

                else:

                    knowledge_context = "\n".join(
                        str(document)
                        for document in documents
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
