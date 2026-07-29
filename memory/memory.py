"""
MemoryStore handles:
- saving memories
- retrieving relevant memories
- ranking memories
- deleting memories

Uses SQLite underneath.
"""


import json
import logging


logger = logging.getLogger("cynx.memory")





class MemoryStore:


    def __init__(
        self,
        conn
    ):

        self.conn = conn







    # ---------------------------------
    # Add Memory
    # ---------------------------------


    def add_memory(
        self,
        content,
        kind="fact",
        importance=5,
        tags=None,
        user_id="default",
        metadata=None
    ):


        cur = self.conn.cursor()


        cur.execute(
            """
            INSERT INTO memories
            (
                user_id,
                kind,
                content,
                importance,
                tags,
                metadata
            )

            VALUES (?, ?, ?, ?, ?, ?)

            """,

            (
                user_id,
                kind,
                content,
                importance,
                json.dumps(tags or []),
                json.dumps(metadata or {})
            )

        )


        self.conn.commit()


        return cur.lastrowid







    # ---------------------------------
    # Search Memory
    # ---------------------------------


    def search(
        self,
        user_id,
        query,
        limit=5
    ):


        words = query.lower().split()


        cur = self.conn.cursor()



        cur.execute(
            """
            SELECT

                id,
                kind,
                content,
                importance,
                tags

            FROM memories

            WHERE user_id=?

            """,

            (
                user_id,
            )

        )



        memories = []



        for row in cur.fetchall():


            memory_text = row[2].lower()


            score = 0



            # keyword matching

            for word in words:


                if word in memory_text:


                    score += 1





            # importance boost

            score += row[3] * 0.1






            if score > 0:


                memories.append(

                    {
                        "id": row[0],

                        "kind": row[1],

                        "content": row[2],

                        "importance": row[3],

                        "score": score

                    }

                )







        memories.sort(

            key=lambda x: x["score"],

            reverse=True

        )





        # return prompt-friendly text

        return [

            memory["content"]

            for memory in memories[:limit]

        ]









    # ---------------------------------
    # Retrieve Raw Context
    # ---------------------------------


    def retrieve_context(
        self,
        query,
        limit=5,
        user_id="default"
    ):


        results = self.search(

            user_id,

            query,

            limit

        )


        return results







    # ---------------------------------
    # Recent Memories
    # ---------------------------------


    def recent(
        self,
        limit=10
    ):


        cur = self.conn.cursor()


        cur.execute(
            """
            SELECT *

            FROM memories

            ORDER BY created_at DESC

            LIMIT ?

            """,

            (
                limit,
            )

        )


        return cur.fetchall()








    # ---------------------------------
    # Delete Memory
    # ---------------------------------


    def delete_memory(
        self,
        memory_id
    ):


        cur = self.conn.cursor()


        cur.execute(
            """
            DELETE FROM memories

            WHERE id=?

            """,

            (
                memory_id,
            )

        )


        self.conn.commit()