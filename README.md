# Predicting Conference Rankings for Academic Papers

Can you tell where a scientific paper will be published — or whether it will be
published at all — from its structure and metadata alone, without reading it?

This repository holds the full pipeline built to answer that question: it
harvests arXiv preprints, recovers their eventual publication venue through
DBLP, labels each venue with its CORE 2023 rank, extracts structural features
from the PDFs, and trains a classifier to predict the rank.

**The short answer is no.** The metrics we extracted turned out not to be good
predictors. That negative result is the main finding, and it is documented in
[Results](#results).

## Context

This work was carried out as a *PIDR* (**P**rojet d'**I**nitiation à la
**D**émarche de **R**echerche — Introduction to Research Methodology project), a
second-year research project at Télécom Nancy. The goal of a PIDR is to run a
small but complete research cycle: formulate a question, build the tooling,
collect the data, run the experiments, and report honestly on what came out —
including when the hypothesis does not hold.

### The problem

Preprint servers have made it trivial to publish, and arXiv alone now hosts
millions of articles with thousands added monthly. Peer review does not scale at
that rate, and researchers have no cheap way to tell which preprints are worth
their attention. We framed this as a multi-class classification task:

```
f : X → Y        Y = { A*, A, B, C, UnRanked }
```

where `X` is a feature space derived from a paper's structure and metadata, and
`Y` is the CORE rank of the venue the paper was eventually published in. A paper
with no DBLP match, or published at a venue CORE does not rank, is labelled
`UnRanked`.

The hypothesis under test was that surface-level signals — page count, reference
count, number of figures, abstract readability, author seniority — correlate
with the quality tier of the venue a paper reaches.

## Pipeline

```
   arXiv API                DBLP                  CORE 2023
 (cs.AI, 2018-2023)   (was it published?)   (how good is that venue?)
         |                    |                        |
         v                    v                        v
   metadata + PDFs  ---> venue + DBLP key  --->  rank (A*/A/B/C/UnRanked)
         |                                             |
         v                                             v
   feature extraction  ------------------------>  Random Forest
   (PyMuPDF, GROBID,                             (scikit-learn)
    textstat, scholarly)                               |
                                                       v
                                             predicted publication rank
```

Every stage writes back into a single MongoDB collection, so features can be
added incrementally without reprocessing the whole corpus.

### 1. Corpus acquisition

A 10% random sample of `cs.AI` submissions per year from 2018 to 2023, pulled
from the arXiv API — **6,282 articles**.

The arXiv API exposes direct PDF links, but bulk retrieval triggers CAPTCHA
protection. The downloader therefore drives the browser's native *Save As*
dialog instead, which reproduces a human-paced download: roughly 464 papers per
hour, about 14 hours of continuous running, and **~10 GB** of PDFs.

### 2. arXiv to DBLP matching

Title formatting differs enough between the two sources that exact matching
performs poorly, so matching is a three-step cascade (`matching/match_arxiv_dblp.py`):

| Step | Method | Accept threshold |
|------|--------|------------------|
| 1 | DBLP REST API, search by title | fuzzy score >= 90 |
| 2 | DBLP SPARQL endpoint, keyword regex on title | fuzzy score >= 90 |
| 3 | DBLP REST API, search by author, then match titles | fuzzy score >= 70 |

The `deepness` argument controls how far the cascade runs (1 = title only,
2 = title + SPARQL, 3 = all three).

### 3. DBLP to CORE matching

The CORE portal is scraped once to attach a DBLP source link to every ranked
venue. Each article is then ranked in two stages
(`matching/match_dblp_core.py`): an exact match on the DBLP conference
identifier first, falling back to fuzzy matching on the venue's full name or
acronym (threshold 80). No match means `UnRanked`.

### 4. Features

| Feature | Source | Description |
|---------|--------|-------------|
| `abstract_size` | arXiv API | Abstract length in words |
| `number_of_authors` | arXiv API | Size of the authorship team |
| `version` | arXiv ID | Number of submission revisions |
| `character` | PyMuPDF | Full-text character count |
| `page` | PyMuPDF | Page count |
| `image` | PyMuPDF | Number of embedded figures |
| `reference` | GROBID | Number of bibliographic references |
| `summary_gunning_fog_score` | textstat | Gunning Fog readability of the abstract |
| `hindex_average` | scholarly | Mean h-index of the authors |

An h-index was resolved for at least one author in 87% of papers; the rest
default to 0.

## Data

**No data is committed to this repository.** The corpus is ~10 GB of PDFs plus
third-party datasets that are not ours to redistribute. Everything is
reconstructed by running the pipeline:

| What | Where it comes from |
|------|---------------------|
| Article metadata | arXiv API, via `fetch_articles_by_years()` |
| PDF files (~10 GB) | arXiv, via `create_pdf_folder_and_download()`, into `data/pdf/` |
| `CORE2023.csv` | [CORE portal](https://portal.core.edu.au/conf-ranks/) export |
| Enriched corpus | MongoDB — built up by the `database/` and `matching/` stages |

`data/` is listed in `.gitignore` in full.

## Repository structure

```
.
├── common/
│   ├── mongo.py                        MongoDB connection (credentials from env)
│   └── batch.py                        Shared batch runner with progress + ETA
├── database/
│   └── database_enrichment.py          arXiv harvesting, PDF stats, CORE scraping,
│                                       readability, h-index, GROBID references,
│                                       and the LLM prompting experiments
├── matching/
│   ├── match_arxiv_dblp.py             Three-step arXiv to DBLP matcher
│   ├── match_dblp_core.py              DBLP venue to CORE rank lookup
│   ├── update_arxiv_dblp_matching.py   Applies the matcher across the corpus
│   └── update_dblp_core_matching.py    Applies the ranker across the corpus
├── pdf_processing/
│   ├── pdf_windows_arxiv.py            Browser-automation PDF downloader (Windows)
│   └── parser_pdf.py                   Offline PDF feature extraction
├── training_model/
│   └── publication_predictor.py        Random Forest training and evaluation
└── requirements.txt
```

## Getting started

### Requirements

- Python 3.10+
- A MongoDB instance (the project used MongoDB Atlas)
- A [GROBID](https://github.com/kermitt2/grobid) server on `localhost:8070`,
  only for reference counting
- An OpenAI API key, only for the LLM experiments
- Windows, only for the PDF downloader — it drives the keyboard and mouse

### Install

```bash
git clone https://github.com/NathanPLONTZ/pidr-article-rank-prediction.git
cd pidr-article-rank-prediction

python -m venv env
source env/bin/activate      # Linux/macOS
env\Scripts\activate         # Windows

pip install -r requirements.txt
```

### Configure

Credentials are read from the environment; nothing is hard-coded.

```bash
export MONGO_USER=your_username
export MONGO_PASSWORD=your_password
```

On Windows PowerShell:

```powershell
$env:MONGO_USER = "your_username"
$env:MONGO_PASSWORD = "your_password"
```

### Run the pipeline

Each stage is a function, meant to be run in order. Every stage only selects
documents still missing the field it computes, so all of them are safe to
interrupt and re-run.

```python
from common.mongo import get_articles_collection
from database.database_enrichment import (
    fetch_articles_by_years, add_pdf_path, create_pdf_folder_and_download,
    update_pdf_info_in_db, update_gunning_fog_all_documents,
    process_documents_add_hindex, add_hindex_average,
    add_version_and_image, add_references_to_all_documents,
)
from matching.update_arxiv_dblp_matching import process_arxiv_dblp_matching
from matching.update_dblp_core_matching import process_dblp_core_matching

collection = get_articles_collection()

# 1. Corpus -> writes articles.json, then import it into MongoDB
fetch_articles_by_years()

# 2. PDFs (Windows only; takes over the keyboard for ~14 h)
add_pdf_path(collection)
create_pdf_folder_and_download(collection)

# 3. Publication venue and rank
process_arxiv_dblp_matching(collection)
process_dblp_core_matching(collection)

# 4. Features
update_pdf_info_in_db(collection)            # pages, characters
add_version_and_image(collection)            # version, figures
update_gunning_fog_all_documents(collection)
process_documents_add_hindex(collection)     # slow: rate-limited by Google Scholar
add_hindex_average(collection)
add_references_to_all_documents(collection)  # needs GROBID running
```

To attach the DBLP source links to a fresh CORE export:

```python
from database.database_enrichment import (
    update_csv_with_dblp_sources, update_csv_with_dblp_ids)

update_csv_with_dblp_sources("data/CORE2023_raw.csv", "data/CORE2023_sources.csv")
update_csv_with_dblp_ids("data/CORE2023_sources.csv", "data/CORE2023.csv")
```

### Train the model

```bash
python -m training_model.publication_predictor
```

This balances the corpus across ranks, trains a Random Forest (100 estimators),
prints a classification report, a confusion matrix and cross-validated accuracy,
then shows the confusion matrix and feature importance plots. Edit
`SAMPLES_PER_RANK` at the top of the file to change the balance — removing the
`UnRanked` entry reproduces the ranked-papers-only experiment described below.

### Analyse PDFs without a database

```python
from pdf_processing.parser_pdf import process_pdfs, verify_pdf_analysis

process_pdfs("data/pdf", "pdf_analysis.json")
verify_pdf_analysis("data/pdf", "pdf_analysis.json")
```

## Results

### Experiment 1 — all five classes

Random Forest, 100 estimators, 80/20 stratified split over 6,282 articles.

| Rank | Precision | Recall | F1-score | Support |
|------|-----------|--------|----------|---------|
| A* | 0.45 | 0.37 | 0.41 | 210 |
| A | 0.20 | 0.02 | 0.04 | 97 |
| B | 0.44 | 0.04 | 0.07 | 200 |
| C | 0.00 | 0.00 | 0.00 | 54 |
| UnRanked | 0.58 | 0.91 | 0.71 | 639 |

10-fold cross-validation: **53.9% accuracy (± 1.0%)** — but macro-averaged
precision, recall and F1 of only **26.6% / 24.4% / 21.3%**.

That gap is the whole story. The headline accuracy is an artefact of class
imbalance: the model learns to answer `UnRanked` almost always (0.91 recall),
and most genuinely ranked papers are swept into that class. It never once
correctly identified a C-ranked paper.

### Experiment 2 — ranked papers only

The `UnRanked` class carries real label noise: papers from 2018–2023 marked
unranked had in several cases been published at ranked venues *after* 2023,
outside the window of our ground truth. Dropping the class removes that
distortion.

| Rank | Precision | Recall | F1-score | Support |
|------|-----------|--------|----------|---------|
| A* | 0.51 | 0.67 | 0.58 | 226 |
| A | 0.15 | 0.04 | 0.06 | 102 |
| B | 0.45 | 0.57 | 0.50 | 209 |
| C | 0.00 | 0.00 | 0.00 | 56 |

Overall accuracy 46.4% on the single split; 10-fold cross-validation gives
**50.4% (± 2.9%)**, ranging from 47.3% to 56.9% across folds.

The classifier separates the extremes — A* and B — with moderate success, and
remains unable to recognise A or C papers at all. It tends to collapse A into A*
and C into B, which suggests it is picking up a coarse "long, dense, well-cited
paper" signal rather than anything about venue tier.

### Which features mattered

Character count dominated, by a wide margin, followed by abstract size, Gunning
Fog score and average h-index. Reference count contributed moderately. Number of
authors and version number were the least informative. Removing `UnRanked` did
not change this ordering.

In other words, the most predictive feature is simply **how long the paper is** —
a proxy for writing style and document structure, not for the quality of the
venue that accepted it.

### LLM evaluation

As an alternative, GPT-4o mini was asked to assess papers directly, using seven
prompting strategies (tagged review with scores, free-form review with scores,
review with a single score, direct scoring, review with an editorial decision,
direct editorial decision, and percentile estimation). Each was run on three A*
papers and three C papers — the opposite ends of the quality spectrum. The exact
prompts are in `PROMPT` in `database/database_enrichment.py`.

| Prompt approach | A* papers | C papers |
|-----------------|-----------|----------|
| Multi-dimensional scores (1–5) | High (4–5) | High (4–5) |
| Review + single score (1–10) | 7–8 | 8 |
| Direct score (1–10) | 8 | 8 |
| Editorial decision | Minor/Major Revision | Minor/Major Revision |
| Percentile estimate | 10–15 | 10–15 |

**Not one strategy separated A* from C papers.** The model scored C papers as
highly as A* papers — in the single-score case, slightly higher. The reviews read
as fluent and plausible while carrying no discriminative signal, and showed a
consistent positive bias.

### Conclusion

Neither approach works. Structural and metadata features are insufficient
proxies for research quality, and an LLM prompted directly is no better. The
features extracted here — length, figures, references, readability, author
h-index — capture presentation, not contribution.

The LLM arm rests on six papers, so that result is indicative rather than
conclusive. The classifier result rests on the full 6,282-paper corpus.

Caveats worth stating plainly:

- **Content-agnostic.** The features describe shape, not substance.
- **Single domain.** Only cs.AI; other fields have other conventions.
- **Noisy ground truth.** CORE ranks are themselves subjective, and the 2023
  snapshot cannot know about publications that happened later.
- **Circularity risk.** Had structural features worked, filtering submissions on
  them would reinforce existing conventions rather than surface unusual work.

Directions that look more promising: semantic analysis of the actual content,
citation and post-publication impact signals, domain-adapted models, and hybrid
systems that assist human reviewers rather than replace them.

## Author

Nathan PLONTZ — Télécom Nancy, 2025.
