"""Random Forest classifier predicting the CORE rank of an arXiv preprint.

Reads the enriched articles from MongoDB, balances the corpus across ranks,
trains a Random Forest on the structural and metadata features, and reports a
classification report, a confusion matrix and the feature importances.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import cross_val_score, train_test_split

from common.mongo import get_articles_collection

# Number of articles to draw for each rank. If the corpus holds fewer, every
# available article of that rank is used. Removing the 'UnRanked' entry
# reproduces the ranked-papers-only experiment.
SAMPLES_PER_RANK = {
    'A*': 268,
    'A': 268,
    'B': 268,
    'C': 268,
    'UnRanked': 268
}

# Features extracted by the enrichment stage and fed to the classifier.
SELECTED_FEATURES = [
    'abstract_size',
    'number_of_authors',
    'character',
    'page',
    'image',
    'version',
    'reference',
    'summary_gunning_fog_score',
    'hindex_average'
]

LABELS_ORDER = ['A*', 'A', 'B', 'C', 'UnRanked']
RANDOM_STATE = 42
CV_FOLDS = 10


def load_articles(collection):
    """
    Loads every article from the collection, keeping only the target column and
    the candidate features.

    Args:
        collection (pymongo.collection.Collection): MongoDB collection.

    Returns:
        pandas.DataFrame: One row per article.
    """
    projection = {'_id': 0, 'core_publication_rank': 1}
    projection.update({feature: 1 for feature in SELECTED_FEATURES})
    return pd.DataFrame(list(collection.find({}, projection)))


def balance_by_rank(df):
    """
    Normalises the target column and draws a fixed number of articles per rank,
    so that no single rank dominates the training set.

    Args:
        df (pandas.DataFrame): Articles with a 'core_publication_rank' column.

    Returns:
        pandas.DataFrame: The balanced sample.
    """
    df = df.copy()
    df['core_publication_rank'] = (
        df['core_publication_rank'].fillna('UnRanked').replace('', 'UnRanked')
    )
    df = df[df['core_publication_rank'].isin(SAMPLES_PER_RANK)]

    sampled_frames = []
    for rank, n in SAMPLES_PER_RANK.items():
        group = df[df['core_publication_rank'] == rank]
        # Take everything available when the corpus holds fewer than n articles.
        sampled = group.sample(n, random_state=RANDOM_STATE) if len(group) >= n else group
        sampled_frames.append(sampled)

    return pd.concat(sampled_frames).reset_index(drop=True)


def build_feature_matrix(df):
    """
    Keeps the configured features that are present and strictly numeric.

    Args:
        df (pandas.DataFrame): The balanced sample.

    Returns:
        pandas.DataFrame: The numeric feature matrix.
    """
    X = df[[col for col in SELECTED_FEATURES if col in df.columns]]

    numeric_features = [
        col for col in X.columns
        if X[col].apply(lambda value: isinstance(value, (int, float))).all()
    ]
    return X[numeric_features]


def plot_confusion_matrix(cm, labels):
    """Displays the confusion matrix as an annotated heatmap."""
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=labels, yticklabels=labels)
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.title("Confusion Matrix - core_publication_rank")
    plt.tight_layout()
    plt.show()


def plot_feature_importances(feature_names, importances):
    """Displays the Random Forest feature importances as a horizontal bar chart."""
    plt.figure(figsize=(8, 5))
    plt.barh(feature_names, importances)
    plt.xlabel("Feature Importance")
    plt.title("Random Forest Feature Importances")
    plt.tight_layout()
    plt.show()


def main():
    """Runs the full training and evaluation pipeline."""
    collection = get_articles_collection()

    df = load_articles(collection)
    if df.empty:
        print("No articles found in the database.")
        return

    df = balance_by_rank(df)

    y = df['core_publication_rank']
    print("Target variable distribution after sampling:\n", y.value_counts())

    X = build_feature_matrix(df)
    print("Numeric features used for training:", X.columns.tolist())

    # Stratification needs at least two samples in every class.
    stratify = y
    if y.value_counts().min() < 2:
        print("Not enough samples for one of the classes. Skipping stratification.")
        stratify = None

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=stratify
    )
    print("Training and testing sets created.")

    clf = RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE)
    clf.fit(X_train, y_train)
    print("Model trained.")

    y_pred = clf.predict(X_test)
    labels_order = [rank for rank in LABELS_ORDER if rank in SAMPLES_PER_RANK]
    cm = confusion_matrix(y_test, y_pred, labels=labels_order)

    print("Confusion Matrix (raw):\n", cm)
    print("\nClassification Report:\n", classification_report(y_test, y_pred))

    # A single split is noisy on a corpus this small, so report cross-validated
    # accuracy as well.
    scores = cross_val_score(
        RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE),
        X, y, cv=CV_FOLDS
    )
    print(f"\n{CV_FOLDS}-fold cross-validation accuracy: "
          f"{scores.mean():.3f} (+/- {scores.std():.3f})")

    plot_confusion_matrix(cm, labels_order)
    plot_feature_importances(X.columns, clf.feature_importances_)


if __name__ == "__main__":
    main()
