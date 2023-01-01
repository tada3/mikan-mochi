#!/bin/bash

# same as in setup_svc_acct.sh and call_cr.sh
NAME=ingest-flights-monthly
PROJECT_ID=$(gcloud config get-value project)
REGION=asia-southeast1
BUCKET=${PROJECT_ID}-biwako
SVC_ACCT=svc-monthly-ingest
SVC_EMAIL=${SVC_ACCT}@${PROJECT_ID}.iam.gserviceaccount.com
SVC_PRINCIPAL=serviceAccount:${SVC_ACCT}@${PROJECT_ID}.iam.gserviceaccount.com

SVC_URL=$(gcloud run services describe ingest-flights-monthly --region ${REGION} --format 'value(status.url)')
echo $SVC_URL
echo $SVC_EMAIL

# note that there is no year or month. The service looks for next month in that case.
echo {\"bucket\":\"${BUCKET}\"\} > /tmp/message
cat /tmp/message

gcloud scheduler jobs create http monthlyupdate \
	   --location=${REGION} \
       --description "Ingest flights using Cloud Run" \
       --schedule="8 of month 10:00" --time-zone "Asia/Tokyo" \
       --uri=$SVC_URL --http-method POST \
       --oidc-service-account-email $SVC_EMAIL --oidc-token-audience=$SVC_URL \
       --max-backoff=7d \
       --max-retry-attempts=5 \
       --max-retry-duration=2d \
       --min-backoff=12h \
       --headers="Content-Type=application/json" \
       --message-body-from-file=/tmp/message


# To try this out, go to Console and do two things:
#    in Service Accounts, give yourself the ability to impersonate this service account (ServiceAccountUser)
#    in Cloud Scheduler, click "Run Now"

# Console -> Cloud Scheduler で "Force a job run" を実行するとエラーになる。
#ログを見ると "PERMISSION DENIED"

#上のコメントに書いてるtことをやってみる。

# Console -> Service Account -> Manage Permissions for 'svc-monthly-ingest' ->
#   Grant Access -> Set 'Service Account User' to 'kuzukiri7'

#しかし、これをやっても結果は同じく "PERMISSION DENIED"。

# Cloud RunのPermissionsを見てみると "svc-monthly-ingest" のエントリーがない。
# 02_deploy_cr.sh でオプションに --service-account つけてたのになー。
# よくわからんけどつけてみる。

gcloud run services add-iam-policy-binding ${NAME} \
	--region=${REGION} \
    --member=${SVC_PRINCIPAL} \
    --role=roles/run.invoker

# これを実行するとConsole -> Cloud Run -> Permissionsで"Cloud Run Invoker"のエントリーが追加されていた。

# あらためて、Cloud Schedulerで直接実行すると成功した。

