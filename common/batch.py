"""Generic batch runner shared by the enrichment stages.

Both matching stages walk a batch of not-yet-processed articles, call a slow
remote service for each one, write the result back and display a progress bar
with an estimated remaining time. That loop lives here once.
"""

import time

from tqdm import tqdm


def run_batch_update(collection, query, projection, handler, description,
                     batch_size=6000, empty_message="No new articles to process."):
    """
    Process a batch of articles and write the computed fields back to MongoDB.

    Args:
        collection (pymongo.collection.Collection): The MongoDB collection of articles.
        query (dict): Filter selecting the articles that still need processing.
        projection (dict): Fields to load for each article.
        handler (callable): Called with one article document. Returns a dict of
            fields to store with '$set', or None to skip the article entirely
            (no database write and no progress bar tick).
        description (str): Label shown on the progress bar.
        batch_size (int): Maximum number of articles to process in a single run.
        empty_message (str): Message printed when no article matches the query.
    """
    articles_to_process = list(collection.find(query, projection).limit(batch_size))

    if not articles_to_process:
        print(empty_message)
        return

    time_start = time.time()
    time_estimates = []

    with tqdm(total=len(articles_to_process), desc=description, unit="paper",
              leave=True, dynamic_ncols=True) as pbar:
        for i, article in enumerate(articles_to_process, 1):
            start_time = time.time()

            updates = handler(article)
            if updates is None:
                continue

            elapsed_time = time.time() - start_time
            time_estimates.append(elapsed_time)

            # Estimate remaining time
            avg_time_per_paper = sum(time_estimates) / len(time_estimates)
            remaining_papers = len(articles_to_process) - i
            estimated_remaining_time = remaining_papers * avg_time_per_paper

            collection.update_one({"_id": article["_id"]}, {"$set": updates})

            pbar.update(1)
            pbar.set_postfix({
                "Estimated Remaining Time": time.strftime(
                    "%H:%M:%S", time.gmtime(estimated_remaining_time))
            })

    time_end = time.time()
    print(f"\nSuccessfully processed {len(articles_to_process)} articles.")
    print(f"Total processing time: {time_end - time_start:.2f} seconds.")
