"""
MemoryStore

Handles:
- adding memories
- searching memories
- retrieving recent memories
- deleting memories

Uses SQLite underneath.
"""


import json





class MemoryStore:



    def __init__(
        self,
        conn
    ):

        self.conn = conn





        print("===== MEMORY STORE DATABASE CHECK =====")


        cur = self.conn.cursor()


        cur.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            """
        )


        print(
            cur.fetchall()
        )


        print(
            "======================================="
        )








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
    # Memory Search
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



        results = []



        for row in cur.fetchall():


            content = row[2].lower()


            score = 0



            for word in words:


                if word in content:

                    score += 1




            # importance bonus

            score += (

                row[3] * 0.1

            )




            if score > 0:


                results.append(

                    {

                        "id": row[0],

                        "kind": row[1],

                        "content": row[2],

                        "importance": row[3],

                        "score": score

                    }

                )




        results.sort(

            key=lambda x: x["score"],

            reverse=True

        )




        return [

            memory["content"]

            for memory in results[:limit]

        ]









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