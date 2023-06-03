#!/bin/bash

if test "$#" -ne 2; then
   echo "Usage: ./stage_airports_file.sh bucket-name dataset-name"
   echo "   eg: ./stage_airports_file.sh mikan-mochi-biwako kura"
   exit
fi

# mikan-mochi-biwako
BUCKET=$1
# kura
DATASET=$2
PROJECT=$(gcloud config get-value project)

gsutil cp airports.csv.gz gs://${BUCKET}/flights/airports/airports.csv.gz

bq --project_id=$PROJECT load \
   --autodetect --replace --source_format=CSV \
   ${DATASET}.airports gs://${BUCKET}/flights/airports/airports.csv.gz