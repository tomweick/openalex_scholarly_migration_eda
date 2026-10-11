################
### OVERVIEW ###
################

# This script:
# 1. Requests author IDs and then requests all publications of those authors
# 2. Extracts, formats, and minimally cleans the API response data
# 3. Saves publication- and author-level data to PostgreSQL database

# NOTE: Use config.yaml to add your API key and adjust database credentials

# OpenAlex API key can be requested here:
# https://docs.openalex.org/how-to-use-the-api/api-overview

###############
### Imports ###
###############

from itertools import chain
import time
import yaml

import numpy as np

import pandas as pd

import psycopg2
from psycopg2.extras import execute_values

import pyalex as pa
from pyalex import Works, Authors
from pyalex import config

#############
### SETUP ###
#############

config_path = "config.yaml"

with open(config_path) as f:
    cfg = yaml.safe_load(f)

data_ver = cfg["metadata"]["data_ver"]

#################
### API SETUP ###
#################

pa.config.api_key = cfg["api"]["key"]

# Retry settings adapted from pyalex (MIT licensed):
# https://github.com/J535D165/pyalex
config.max_retries = 1
config.retry_backoff_factor = 0.1
config.retry_http_codes = [429, 500, 503]

##########################
### GET RANDOM AUTHORS ###
##########################

data_authors_raw = []

for _ in range(cfg["api"]["authors"]):
    author = Authors().random()
    data_authors_raw.append(dict(author))
    time.sleep(0.1)
    print(f"Author fetched, total: {len(data_authors_raw)}")

#####################################
### EXTRACT IDs AND REQUEST WORKS ###
#####################################

# Extract author IDs from the raw author data

data_authors_id = [author["id"] for author in data_authors_raw]

# Get publication history of authors

data_author_works = {}

for author_ids in data_authors_id:
    works_query = Works().filter(author={"id": author_ids})

    # Pagination allows retrieving more than 25 works per author
    works = list(chain(*works_query.paginate(per_page=200)))

    data_author_works[author_ids] = works

    time.sleep(0.1)
    print(f"Works for author {author_ids} fetched: {len(works)}")

#######################################################
### EXTRACT RELEVANT INFORMATION FROM THE DATA (DF) ###
#######################################################

data_rows = []

for author_id, works in data_author_works.items():
    for work in works:

        # Assign a placeholder
        author_countries = None
        author_institutions = []

        # Loop through authorships to find matching author
        for authorship in work["authorships"]:
            if authorship["author"]["id"] == author_id:
                author_countries = authorship.get("countries")

                # Extract institution display names
                institutions_list = authorship.get("institutions", [])
                for inst in institutions_list:
                    if "display_name" in inst:
                        author_institutions.append(inst["display_name"])
                break  # stop after finding the matching author

        # Append individual rows
        data_rows.append(
            {
                "paper_id": work["id"],
                "person_id": author_id,
                "affiliation_name": author_institutions,
                "time_id": work["publication_date"],
                "countries": author_countries,
                "cited_by_count": work["cited_by_count"],
                "data_ver": data_ver,
            }
        )

df = pd.DataFrame(data_rows)

###########################################
### DATA FORMATING AND MINIMAL CLEANING ###
###########################################

df_collapsed = df.copy()  # Un-exploded version used later

df = df[df["time_id"].notna()]  # Removes works without valid time_id

df["time_id"] = pd.to_datetime(df["time_id"])

df = df[
    df.groupby("person_id")["time_id"].transform("min").dt.year >= 1996
]  # Mitigate censoring issues of migration event inference

df = df[
    df.groupby("person_id")["paper_id"].transform("nunique") >= 2
]  # Mitigate migration inference problems

# Format for the database

df = df.sort_values("time_id")
df = df.explode("countries")
df = df.explode("affiliation_name")

#############################
### Put works in database ###
#############################

# Make missing values PostgreSQL-compatible

to_db = df.copy()

to_db = to_db.replace(["NA", "N/A", "null", ""], None)

conn = psycopg2.connect(
    host=cfg["database"]["host"],
    dbname=cfg["database"]["dbname"],
    user=cfg["database"]["user"],
    password=cfg["database"]["password"],
    port=cfg["database"]["port"],
)

with conn.cursor() as cur:
    cur.execute("DROP TABLE IF EXISTS works;")

    cur.execute("""CREATE TABLE works (
        id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        paper_id VARCHAR(255),
        person_id VARCHAR(255),
        affiliation_name VARCHAR(255),
        time_id DATE,
        countries VARCHAR(255),
        cited_by_count INT,
        data_ver INT
    );
    """)

    query = f"""
        INSERT INTO works ({','.join(to_db.columns)})
        VALUES %s
    """

    execute_values(cur, query, to_db.itertuples(index=False, name=None))

conn.commit()
conn.close()

##############################
### Make author level data ###
##############################

# Create author-level data

df_authors = (
    df.groupby("person_id")
    .agg(
        academic_origin=("countries", "first"), # Location of first publication is considered academic origin
        n_publications=("paper_id", "nunique"),
        publication_span=("time_id", lambda x: (x.max() - x.min()).days / 365.2425),
        helper_n_countries=("countries", "nunique"),  # Not for database
        helper_n_affiliations=("affiliation_name", "nunique"),  # Not for database
        data_ver=("data_ver", "first"),
    )
    .reset_index()
)

# Calculate median citations per author based on df_collapsed

median_citations = (
    df_collapsed.groupby("person_id")["cited_by_count"]
    .median()
    .rename("median_citations")
    .reset_index()
)

df_authors = df_authors.merge(median_citations, on="person_id", how="left")

df_authors["mobility_status"] = np.select(
    [
        df_authors["helper_n_countries"] >= 2,
        (df_authors["helper_n_affiliations"] >= 2)
        & (df_authors["helper_n_countries"] == 1),
        (df_authors["helper_n_affiliations"] == 1)
        & (df_authors["helper_n_countries"] == 1),
    ],
    [
        "international",
        "subnational",
        "immobile",
    ],
    default="unknown",
)

#########################################
### Put author-level data in database ###
#########################################

conn = psycopg2.connect(
    host=cfg["database"]["host"],
    dbname=cfg["database"]["dbname"],
    user=cfg["database"]["user"],
    password=cfg["database"]["password"],
    port=cfg["database"]["port"],
)

with conn.cursor() as cur:
    cur.execute("DROP TABLE IF EXISTS authors;")

    cur.execute("""CREATE TABLE authors (
        id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        person_id VARCHAR(255),
        academic_origin VARCHAR(255),
        n_publications INT,
        median_citations FLOAT,
        publication_span INT,
        mobility_status VARCHAR(255),
        data_ver INT
    );
    """)

    query = """
        INSERT INTO authors (
            person_id,
            academic_origin,
            n_publications,
            median_citations,
            publication_span,
            mobility_status,
            data_ver
        )
        VALUES %s
    """

    execute_values(
        cur,
        query,
        df_authors[
            [
                "person_id",
                "academic_origin",
                "n_publications",
                "median_citations",
                "publication_span",
                "mobility_status",
                "data_ver",
            ]
        ].itertuples(index=False, name=None),
    )

conn.commit()
conn.close()