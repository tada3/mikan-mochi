#!/bin/bash

PROJECT_ID=$(gcloud config get-value project)
BUCKET=${PROJECT_ID}-biwako
REGION=asia-southeast1

gsutil ls gs://$BUCKET || gsutil mb -l $REGION gs://$BUCKET

