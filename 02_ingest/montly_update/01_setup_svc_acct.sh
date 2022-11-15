#!/bin/bash

PROJECT_ID=$(gcloud config get-value project)
BUCKET=${PROJECT_ID}-biwako
REGION=asia-southeast1
DATASET_NAME=kura
SVC_ACCT=svc-monthly-ingest
SVC_PRINCIPAL=serviceAccount:${SVC_ACCT}@${PROJECT_ID}.iam.gserviceaccount.com

gsutil ls gs://$BUCKET || gsutil mb -l $REGION gs://$BUCKET

gcloud iam service-accounts create $SVC_ACCT --display-name "flights monthly ingest"


# Switch to uniform access control
gsutil uniformbucketlevelaccess set on gs://$BUCKET

# make the service account the admin of the bucket
# it can read/write/list/delete etc. on only this bucket
gsutil iam ch ${SVC_PRINCIPAL}:roles/storage.admin gs://$BUCKET


# ability to create/delete partitions etc in BigQuery table
#bq --project_id=${PROJECT_ID} query --nouse_legacy_sql \
#  "GRANT \`roles/bigquery.dataOwner\` ON SCHEMA \`$PROJECT_ID.$DATASET_NAME\` TO '$SVC_PRINCIPAL' "
# Somehow this query gets error:
#   Not found: Dataset mikan-mochi:kura
# Explicitly adding project_id does not work. So as temporary fix, I used console to grant
# priviledge to the service account.
# Sharing -> Permissions -> Add Principal
bq --project_id=${PROJECT_ID} query --nouse_legacy_sql \
  "GRANT \`roles/bigquery.dataOwner\` ON SCHEMA \`$DATASET_NAME\` TO '$SVC_PRINCIPAL' "

# You can see the assigned role in IAM -> (Select Project) -> Permissions
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member ${SVC_PRINCIPAL} \
  --role roles/bigquery.jobUser

