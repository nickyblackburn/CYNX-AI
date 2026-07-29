import json


class KnowledgeStore:


    def __init__(
        self,
        conn
    ):

        self.conn = conn



    # ---------------------------------
    # Add Knowledge
    # ---------------------------------

    def add(
        self,
        content,
        title="",
        category="general",
        importance=5,
        tags=None
    ):


        cur = self.conn.cursor()


        cur.execute(
        """
        INSERT INTO knowledge
        (
            category,
            title,
            content,
            importance,
            tags
        )

        VALUES (?, ?, ?, ?, ?)

        """,
        (
            category,
            title,
            content,
            importance,
            json.dumps(tags or [])
        )
        )


        self.conn.commit()


        return cur.lastrowid



    # ---------------------------------
    # Search Knowledge
    # ---------------------------------

    def search(
        self,
        query,
        limit=5
    ):


        words = query.lower().split()


        cur = self.conn.cursor()


        cur.execute(
        """
        SELECT
            id,
            title,
            content,
            importance

        FROM knowledge

        """
        )


        results=[]


        for row in cur.fetchall():


            text = (
                row[1]
                +
                " "
                +
                row[2]
            ).lower()



            score=0


            for word in words:

                if word in text:

                    score += 1



            score += row[3] * 0.1



            if score > 0:

                results.append(
                {
                    "id":row[0],
                    "title":row[1],
                    "content":row[2],
                    "score":score
                }
                )



        results.sort(
            key=lambda x:x["score"],
            reverse=True
        )


        return [
            x["content"]
            for x in results[:limit]
        ]



    # ---------------------------------
    # Recent Knowledge
    # ---------------------------------

    def recent(
        self,
        limit=10
    ):

        cur=self.conn.cursor()


        cur.execute(
        """
        SELECT *

        FROM knowledge

        ORDER BY created_at DESC

        LIMIT ?

        """,
        (limit,)
        )


        return cur.fetchall()