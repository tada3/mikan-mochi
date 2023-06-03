#!/bin/bash

if test "$#" -ne 2; then
   echo "Usage: ./bqsample.sh dataset-name(source) bucket-name(destination)"
   echo "   eg: ./bqsample.sh cloud-training-demos-ml"
   exit
fi

# kura
DATASET=$1
# mikan-mochi-biwako
BUCKET=$2
PROJECT=$(gcloud config get-value project)

bq --project_id=$PROJECT query --destination_table ${DATASET}.flights_sample_mini --replace --nouse_legacy_sql \
   "SELECT * FROM ${DATASET}.flights WHERE RAND() < 0.0003"

bq --project_id=$PROJECT extract --destination_format=NEWLINE_DELIMITED_JSON \
   ${DATASET}.flights_sample_mini  gs://${BUCKET}/flights/ch4/flights_sample_mini.json

gsutil cp gs://${BUCKET}/flights/ch4/flights_sample_mini.json .
