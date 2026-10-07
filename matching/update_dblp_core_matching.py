"""Enrichment stage: assign a CORE rank to the DBLP venue of each article."""

from common.batch import run_batch_update
from matching.match_dblp_core import get_rank


def process_dblp_core_matching(collection, batch_size=6000):
    """
    Process a batch of articles from the MongoDB collection to match DBLP
    conferences with CORE rankings.

    Articles whose 'dblp_conference' is not a string were never matched against
    DBLP, so they are skipped rather than ranked.

    Args:
        collection (pymongo.collection.Collection): The MongoDB collection of articles.
        batch_size (int): Number of articles to process in a single run.
    """

    def handle(article):
        conference = article["dblp_conference"]
        key = article["dblp_key"]

        if not isinstance(conference, str):
            return None

        conference_match, rank, score_rank, pub_type = get_rank(conference, key)

        return {
            "dblp_core_linked": True,
            "core_publication": conference_match,
            "core_publication_score": score_rank,
            "core_publication_rank": rank,
            "publication_type": pub_type
        }

    run_batch_update(
        collection,
        query={"dblp_core_linked": {"$exists": False}},
        projection={"_id": 1, "dblp_conference": 1, "dblp_key": 1},
        handler=handle,
        description="Matching Papers",
        batch_size=batch_size,
        empty_message="No new articles to process. All have been checked for "
                      "DBLP-CORE matching."
    )
