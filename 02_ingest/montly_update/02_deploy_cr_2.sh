#!/bin/bash

# same as in setup_svc_acct
NAME=ingest-flights-monthly
SVC_ACCT=svc-monthly-ingest
PROJECT_ID=$(gcloud config get-value project)
REGION=asia-southeast1
SVC_EMAIL=${SVC_ACCT}@${PROJECT_ID}.iam.gserviceaccount.com
IMAGE_VERSION=100
TAG=gcr.io/${PROJECT_ID}/${NAME}:${IMAGE_VERSION}
BUCKET_FOR_BUILD=${PROJECT_ID}_mybuild
BUCKET_FOR_ARTIFACTS=gs://artifacts.${PROJECT_ID}.appspot.com

#gcloud run deploy $NAME --region $REGION --source=$(pwd) \
#    --platform=managed --service-account ${SVC_EMAIL} --no-allow-unauthenticated \
#    --timeout 12m \

# 勝手にCloud Storageに mikanmochi_cloudbuild というBucketが作られている。
# https://stackoverflow.com/questions/71250283/gcloud-beta-run-deploy-source-throws-412
# これを参考にした修正版が 02_deploy_cr_2.sh

echo "building.."
gcloud builds submit --tag ${TAG} $(pwd) \
    --gcs-source-staging-dir=gs://${BUCKET_FOR_BUILD}/source \
    --gcs-log-dir=gs://${BUCKET_FOR_BUILD}/log 

echo "deploying.."
gcloud run deploy ${NAME} --image ${TAG} \
    --region ${REGION} --platform=managed \
    --service-account ${SVC_EMAIL} --no-allow-unauthenticated \
    --timeout 12m

# これだと mikan-mochi_cloudbuild (US Multi-region)というBucketは作られない。
# しかし、artifacts.${PROJECT_ID}.appspot.com というBucketは作られてしまう。
# これを防ぐにはcloudbuild.yamlで設定すれば良いみたいだが、そこまではやりたくないので
# とりあえず自動で削除するようにする。

gsutil -m rm -r ${BUKCET_FOR_ARTIFACTS}

