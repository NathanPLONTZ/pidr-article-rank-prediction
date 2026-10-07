"""Enrichment stage: link each ArXiv article in MongoDB to its DBLP entry."""

from common.batch import run_batch_update
from matching.match_arxiv_dblp import match_arxiv_with_dblp


def process_arxiv_dblp_matching(collection, batch_size=6000):
    """
    Process a batch of articles from the MongoDB collection to match ArXiv papers
    with DBLP entries.

    Args:
        collection (pymongo.collection.Collection): The MongoDB collection of articles.
        batch_size (int): Number of articles to process in a single run.
    """

    def handle(article):
        title = article["title"]
        authors = article.get("authors", [])

        is_match, dblp_title, conference, key, score, method = match_arxiv_with_dblp(
            title, authors, deepness=3)

        return {
            "arxiv_dblp_linked": True,
            "matched": is_match,
            "dblp_title": dblp_title,
            "dblp_conference": conference,
            "dblp_key": key,
            "title_matching_score": score,
            "matching_method": method
        }

    run_batch_update(
        collection,
        query={"arxiv_dblp_linked": {"$exists": False}},
        projection={"_id": 1, "title": 1, "authors": 1},
        handler=handle,
        description="Matching Papers",
        batch_size=batch_size,
        empty_message="No new articles to process. All have been checked for "
                      "ArXiv-DBLP matching."
    )
