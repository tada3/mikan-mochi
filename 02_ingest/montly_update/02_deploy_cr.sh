#!/bin/bash

# same as in setup_svc_acct
NAME=ingest-flights-monthly
SVC_ACCT=svc-monthly-ingest
PROJECT_ID=$(gcloud config get-value project)
REGION=asia-southeast1
SVC_EMAIL=${SVC_ACCT}@${PROJECT_ID}.iam.gserviceaccount.com
IMAGE_VERSION=100
TAG=gcr.io/${PROJECT_ID}/${NAME}:${IMAGE_VERSION}

#gcloud functions deploy $URL \
#    --entry-point ingest_flights --runtime python37 --trigger-http \
#    --timeout 540s --service-account ${SVC_EMAIL} --no-allow-unauthenticated

gcloud run deploy $NAME --region $REGION --source=$(pwd) \
    --platform=managed --service-account ${SVC_EMAIL} --no-allow-unauthenticated \
    --timeout 12m \

# 勝手にCloud Storageに mikanmochi_cloudbuild というBucketが作られている。
# https://stackoverflow.com/questions/71250283/gcloud-beta-run-deploy-source-throws-412
# これを参考にした修正版が 02_deploy_cr_2.sh
