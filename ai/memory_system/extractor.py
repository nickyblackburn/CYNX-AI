"""
MemoryExtractor

Extracts important information from conversations:
- preferences
- goals
- projects
- names
- communication style

Saves through MemoryStore.
"""


import logging
import re
from typing import List


logger = logging.getLogger("cynx.memory")





class MemoryExtractor:


    def __init__(
        self,
        memory_store
    ):

        self.memory_store = memory_store






    # ---------------------------------
    # Extraction
    # ---------------------------------


    def extract_and_save(
        self,
        user_id: str,
        user_message: str,
        assistant_response: str = ""
    ) -> List[int]:


        saved_ids = []


        text = (

            user_message

            +

            " "

            +

            assistant_response

        )



        extracted = []





        extracted += [

            (
                "preference",
                item,
                6

            )

            for item in self.extract_preferences(text)

        ]



        extracted += [

            (
                "goal",
                item,
                8

            )

            for item in self.extract_goals(text)

        ]



        extracted += [

            (
                "project",
                item,
                9

            )

            for item in self.extract_projects(text)

        ]



        extracted += [

            (
                "name",
                item,
                10

            )

            for item in self.extract_names(text)

        ]



        extracted += [

            (
                "style",
                item,
                5

            )

            for item in self.extract_style(text)

        ]






        for category, content, importance in extracted:



            if not self.should_save(content):

                continue





            memory_id = self.memory_store.add_memory(

                user_id=user_id,

                kind=category,

                content=content,

                importance=importance,

                tags=[category],

                metadata={

                    "source": "memory_extractor"

                }

            )



            saved_ids.append(

                memory_id

            )






        if saved_ids:


            logger.info(

                f"[MEMORY] Saved {len(saved_ids)} memories"

            )



        return saved_ids







    # ---------------------------------
    # Extractors
    # ---------------------------------


    def extract_preferences(
        self,
        text
    ):


        patterns = [

            r"i (?:like|love|prefer|enjoy|hate|dislike) ([^.!?]+)"

        ]


        return self.match_patterns(

            patterns,

            text,

            "Prefers"

        )






    def extract_goals(
        self,
        text
    ):


        patterns = [

            r"(?:i want to|my goal is|i am trying to) ([^.!?]+)"

        ]


        return self.match_patterns(

            patterns,

            text,

            "Goal"

        )







    def extract_projects(
        self,
        text
    ):


        patterns = [

            r"(?:building|creating|working on|developing) ([^.!?]+)"

        ]


        return self.match_patterns(

            patterns,

            text,

            "Project"

        )







    def extract_names(
        self,
        text
    ):


        matches = re.findall(

            r"(?:my name is|call me) ([A-Za-z ]+)",

            text,

            re.IGNORECASE

        )


        return [

            f"Name: {x.strip()}"

            for x in matches

        ]







    def extract_style(
        self,
        text
    ):


        patterns = [

            r"i prefer (.+?) explanations",

            r"i like (.+?) answers"

        ]


        return self.match_patterns(

            patterns,

            text,

            "Style"

        )








    # ---------------------------------
    # Helpers
    # ---------------------------------


    def match_patterns(
        self,
        patterns,
        text,
        prefix
    ):


        results = []


        for pattern in patterns:


            matches = re.findall(

                pattern,

                text,

                re.IGNORECASE

            )



            for match in matches:


                value = match.strip()



                if self.meaningful(value):


                    results.append(

                        f"{prefix}: {value}"

                    )



        return results[:3]







    def meaningful(
        self,
        text
    ):


        cleaned = re.sub(

            r"[^a-zA-Z0-9 ]",

            "",

            text

        )


        return len(cleaned.strip()) >= 3






    def should_save(
        self,
        content
    ):


        if not content:

            return False



        if len(content) < 5:

            return False



        if not re.search(

            r"[a-zA-Z0-9]",

            content

        ):

            return False



        return True