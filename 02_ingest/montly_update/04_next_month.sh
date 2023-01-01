#!/bin/bash

# same as deploy_cr.sh
NAME=ingest-flights-monthly

PROJECT_ID=$(gcloud config get-value project)
REGION=asia-southeast1
BUCKET=${PROJECT_ID}-biwako

URL=$(gcloud run services describe ingest-flights-monthly --region ${REGION} --format 'value(status.url)')
echo $URL

# next month
echo "Getting month that follows ... (removing 12 if needed, so there is something to get) "
gsutil rm -rf gs://$BUCKET/flights/raw/201512.csv.gz
gsutil ls gs://$BUCKET/flights/raw
echo {\"bucket\":\"${BUCKET}\"\} > /tmp/message
cat /tmp/message

curl -k -X POST $URL \
   -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
   -H "Content-Type:application/json" --data-binary @/tmp/message

echo "Done"
