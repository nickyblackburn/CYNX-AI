"""
ContextManager handles:
- memory retrieval
- knowledge retrieval
- identity context

Keeps ChatEngine clean.
Returns structured context for PromptBuilder.
"""


import logging


logger = logging.getLogger("cynx.context")




class ContextManager:


    def __init__(
        self,
        memory_store,
        knowledge_store
    ):

        self.memory_store = memory_store

        self.knowledge_store = knowledge_store






    # ---------------------------------
    # Context Builder
    # ---------------------------------


    def build_context(
        self,
        user_id: str,
        user_message: str
    ):


        memory_context = ""

        knowledge_context = ""





        # -----------------------------
        # Identity
        # -----------------------------


        identity = self.get_identity()






        # -----------------------------
        # Memory Retrieval
        # -----------------------------


        try:


            memories = self.memory_store.search(

                user_id,

                user_message,

                limit=5

            )



            if memories:


                memory_context = "\n".join(

                    memories

                )



            logger.info(

                f"[MEMORY] Retrieved {len(memories)} items"

            )



        except Exception as e:


            logger.error(

                f"[MEMORY ERROR] {e}"

            )







        # -----------------------------
        # Knowledge Retrieval
        # -----------------------------


        try:


            documents = self.knowledge_store.search(

                user_message,

                limit=3

            )



            if documents:


                knowledge_context = "\n".join(

                    documents

                )



            logger.info(

                f"[KNOWLEDGE] Retrieved {len(documents)} items"

            )



        except Exception as e:


            logger.error(

                f"[KNOWLEDGE ERROR] {e}"

            )








        # -----------------------------
        # Return Structured Context
        # -----------------------------


        return {


            "identity":

                identity,


            "memory":

                memory_context,


            "knowledge":

                knowledge_context


        }







    # ---------------------------------
    # Identity
    # ---------------------------------


    def get_identity(self):


        return """
CYN-X identity:

You are CYN-X.

Maintain:
- playful personality
- curiosity
- analytical thinking
- consistent behavior

Be helpful and conversational.
"""