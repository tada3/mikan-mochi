#!/bin/sh
DATASET='kura'
bq mk --external_table_definition=./airport_schema.json@CSV=gs://data-science-on-gcp/edition2/raw/airports.csv ${DATASET}.airports_gcs
