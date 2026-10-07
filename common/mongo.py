"""Single entry point for every MongoDB connection used by the pipeline.

Credentials are never hard-coded: they are read from the MONGO_USER and
MONGO_PASSWORD environment variables.
"""

import os

from pymongo import MongoClient
from pymongo.server_api import ServerApi

CLUSTER = "pidr.jtdn1.mongodb.net"
DATABASE_NAME = "ArticleDB"
COLLECTION_NAME = "Articles"
APP_NAME = "PIDR"


def get_articles_collection(username=None, password=None):
    """
    Connect to the MongoDB Atlas cluster and return the 'Articles' collection
    of the 'ArticleDB' database.

    Args:
        username (str, optional): MongoDB username. Defaults to the MONGO_USER
            environment variable.
        password (str, optional): MongoDB password. Defaults to the
            MONGO_PASSWORD environment variable.

    Returns:
        pymongo.collection.Collection: The 'Articles' collection.

    Raises:
        RuntimeError: If no credentials are provided and the environment
            variables are not set.
    """
    username = username or os.environ.get("MONGO_USER")
    password = password or os.environ.get("MONGO_PASSWORD")

    if not username or not password:
        raise RuntimeError(
            "MongoDB credentials are missing. Set the MONGO_USER and "
            "MONGO_PASSWORD environment variables, or pass them explicitly."
        )

    uri = (
        f"mongodb+srv://{username}:{password}"
        f"@{CLUSTER}/?retryWrites=true&w=majority&appName={APP_NAME}"
    )
    client = MongoClient(uri, server_api=ServerApi('1'))
    db = client[DATABASE_NAME]
    return db[COLLECTION_NAME]
