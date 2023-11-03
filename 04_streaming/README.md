# 4. Streaming data: publication and ingest

PROJECT=$(gcloud config get-value project)
BUCKETNAME=mikan-mochi-biwako
DATASETNAME=kura

### Catch up until Chapter 3 if necessary
* Go to the Storage section of the GCP web console and create a new bucket
* Open CloudShell and git clone this repo:
    ```
    git clone https://github.com/GoogleCloudPlatform/data-science-on-gcp
    ```
* Then, run:
```
cd data-science-on-gcp/02_ingest
./ingest_from_crsbucket bucketname
```
* Run:
```
cd ../03_sqlstudio
./create_views.sh
```

### Batch processing transformation in DataFlow
* Setup:
    ```
	cd transform; ./install_packages.sh
    ```
* Parsing airports data:
	```
	./df01.py
	head extracted_airports-00000*
	rm extracted_airports-*
	```
* Adding timezone information:
	```
	./df02.py
	head airports_with_tz-00000*
	rm airports_with_tz-*
	```
* Create sample data
	```
	bash bqsample.sh kura mikan-mochi-biwako
	```

* Converting times to UTC:
	```
	./df03.py
	head -3 all_flights-00000*
	```
* Correcting dates:
	```
	./df04.py
	head -3 all_flights-00000*
	rm all_flights-*
	```
* Create events:
	```
	./df05.py
	head -3 all_events-00000*
	rm all_events-*
	```  
* Read/write to Cloud:
	```
    ./stage_airports_file.sh BUCKETNAME
	./df06.py --project PROJECT --bucket BUCKETNAME --dataset DATASETNAME
	``` 

	If you get an errror like this:
	   WARNING:apache_beam.internal.gcp.auth:Unable to find default credentials to use: Could not automatically determine credentials. Please set GOOGLE_APPLICATION_CREDENTIALS or explicitly create credentials and re-run the application. For more information, please see https://cloud.google.com/docs/authentication/getting-started
	try `gcloud auth application-default login` 

    Look for new tables in BigQuery (flights_simevents)



* Run on Cloud:
	```
	./df07.py --project $PROJECT --bucket $BUCKETNAME --region asia-southeast1 --dataset $DATASETNAME
	``` 

	これだと以下のようなエラーが出てjobが失敗する。

	```
	Startup of the worker pool in zone asia-southeast1-c failed to bring up any of the desired 1 workers. Please refer to https://cloud.google.com/dataflow/docs/guides/common-errors#worker-pool-failure for help troubleshooting. ZONE_RESOURCE_POOL_EXHAUSTED: Instance 'ch04timecorr-08131712-r5ob-harness-wxff' creation failed: The zone 'projects/mikan-mochi/zones/asia-southeast1-c' does not have enough resources available to fulfill the request. Try a different zone, or try again later.
	```

	たいしたリソースでもないので何かの設定ミスだと思ったけど、一応GCP側の問題の可能性もあるので、asia-east1で試してみる。

	```
	python3 df07.py --project $PROJECT --bucket $BUCKETNAME --region asia-east1 --dataset $DATASETNAME
	``` 

	すると、ちゃんとworkerが割り当てられrた！なんやねん。

	リソース不足が原因かと思て、--max_num_workers=1にしてたのでめっちゃ遅い。
	ちゃんと、

	```
	このジョブは自動スケーリングを使用しており、CPU 使用率（84%）が高く、ワーカーの最大数設定（1）を使用しています。最大数を増やすとパフォーマンスが向上する可能性があります。
	```
	と警告を出してくれたので、8に戻す。

	datasetがdsongcpのままになっているところがあったので、そこがエラーになったが、それを修正したら、成功した。でも、実行時間が1時間13分もかかってる。(コンソール上で)


	



* Go to the GCP web console and wait for the Dataflow ch04timecorr job to finish. It might take between 30 minutes and 2+ hours depending on the quota associated with your project (you can change the quota by going to https://console.cloud.google.com/iam-admin/quotas).
* Then, navigate to the BigQuery console and type in:
	```
        SELECT
          ORIGIN,
          DEP_TIME,
          DEST,
          ARR_TIME,
          ARR_DELAY,
          EVENT_TIME,
          EVENT_TYPE
        FROM
          kura.flights_simevents
        WHERE
          (DEP_DELAY > 15 and ORIGIN = 'SEA') or
          (ARR_DELAY > 15 and DEST = 'SEA')
        ORDER BY EVENT_TIME ASC
        LIMIT
          5

	```
### Simulate event stream
* In CloudShell, run
	```
    cd simulate
	python3 ./simulate.py --startTime '2015-05-01 00:00:00 UTC' --endTime '2015-05-04 00:00:00 UTC' --speedFactor=30 --project $PROJECT --dataset $DATASETNAME
    ```

	これだと待ち時間が長いので、speefFactor=240にする。

	```
    cd simulate
	python3 ./simulate.py --startTime '2015-05-01 00:00:00 UTC' --endTime '2015-05-04 00:00:00 UTC' --speedFactor=240 --project $PROJECT --dataset $DATASETNAME
    ```
 
### Real-time Stream Processing
* In another CloudShell tab, run avg01.py:
	```
	cd realtime
	python3 avg01.py --project ${PROJECT} --bucket ${BUCKETNAME} --region hoge --dataset ${DATASETNAME}
	```

	DirectRunnerなのでregionは不要。

	イベントは取れてるけど、最後のイベントが取れてない。

	送信側で、送信完了を待つようにするのと、受信側でログを入れる。これで最後のイベントまで取れるようになった。

	ちなみに、publisher.publish()を呼び出してから、受信側で受信するまで１分から2分位のタイムラグがある。

	```
    cd simulate
	python3 ./simulate.py --startTime '2015-05-03 00:00:00 UTC' --endTime '2015-05-04 00:00:00 UTC' --speedFactor=240 --project $PROJECT --dataset $DATASETNAME
    ```
	
	```
	cd realtime
	python3 avg01.py --project ${PROJECT} --bucket ${BUCKETNAME} --region hoge --dataset ${DATASETNAME}
	```

	#### 送信側の変更

	##### Before
	```
	for event_data in events:
          publisher.publish(topic, event_data.encode(), EventTimeStamp=timestamp)
	```

	##### After
	```
	publish_futures = []

	def check_futures():
   		logging.info('Checking..')
   		for f in publish_futures:
      		print('result', f.result())
			logging.info('Check Done')

	for event_data in events:
        # Need to encode to utf-8 byte array
        future = publisher.publish(topic, event_data.encode(), EventTimeStamp=timestamp)
        publish_futures.append(future)
	```

	#### 受信側の変更
	##### Before
	```
	import logging
    logging.getLogger().setLevel(logging.INFO)

    def log_and_parse_event(s):
        event = json.loads(s)
        logging.info(f'Processing event: {s}')
        return event
	
	events[event_name] = (pipeline
    						| 'read:{}'.format(event_name) >> beam.io.ReadFromPubSub(topic=topic_name)
                            | 'parse:{}'.format(event_name) >> beam.Map(lambda s: json.loads(s))
                			)
	```

	##### After
	```
	events[event_name] = (pipeline
                    		| 'read:{}'.format(event_name) >> beam.io.ReadFromPubSub(topic=topic_name)
                            | 'parse:{}'.format(event_name) >> beam.Map(log_and_parse_event)
                        	)
	```


* In about a minute, you can query events from the BigQuery console:
	```
	SELECT * FROM kura.streaming_events
	ORDER BY EVENT_TIME DESC
    LIMIT 5
	```
* Stop avg01.py by hitting Ctrl+C
* Run avg02.py:
	```
	python3 avg02.py --project ${PROJECT} --bucket ${BUCKETNAME} --region hoge --dataset ${DATASETNAME}
	```
* In about 5 min, you can query from the BigQuery console:
	```
	SELECT * FROM dsongcp.streaming_delays
	ORDER BY END_TIME DESC
    LIMIT 5
	``` 
	全然データがBQのテーブルに書き込まれへん。。
	これが、stuckしてるということなんかな。。
	avg01.pyと同じようにログだしてるけど、テーブルを作りましたというログもでえへんわ。


* Look at how often the data is coming in:
	```
    SELECT END_TIME, num_flights
    FROM dsongcp.streaming_delays
    ORDER BY END_TIME DESC
    LIMIT 5
	``` 
* It's likely that the pipeline will be stuck. You need to run this on Dataflow.
* Stop avg02.py by hitting Ctrl+C
* In BigQuery, truncate the table:
	```
	TRUNCATE TABLE dsongcp.streaming_delays
	``` 
* Run avg03.py:
	```
	python3 avg03.py --project ${PROJECT} --bucket ${BUCKETNAME} --region asia-east1 --dataset ${DATASETNAME}
	```
* Go to the GCP web console in the Dataflow section and monitor the job.
* Once the job starts writing to BigQuery, run this query and save this as a view:
	```
	SELECT * FROM dsongcp.streaming_delays
    WHERE AIRPORT = 'ATL'
    ORDER BY END_TIME DESC
	```
* Create a view of the latest arrival delay by airport:
	```
    CREATE OR REPLACE VIEW dsongcp.airport_delays AS
    WITH delays AS (
        SELECT d.*, a.LATITUDE, a.LONGITUDE
        FROM dsongcp.streaming_delays d
        JOIN dsongcp.airports a USING(AIRPORT) 
        WHERE a.AIRPORT_IS_LATEST = 1
    )
     
    SELECT 
        AIRPORT,
        CONCAT(LATITUDE, ',', LONGITUDE) AS LOCATION,
        ARRAY_AGG(
            STRUCT(AVG_ARR_DELAY, AVG_DEP_DELAY, NUM_FLIGHTS, END_TIME)
            ORDER BY END_TIME DESC LIMIT 1) AS a
    FROM delays
    GROUP BY AIRPORT, LONGITUDE, LATITUDE

	```   
* Follow the steps in the chapter to connect to Data Studio and create a GeoMap.
* Stop the simulation program in CloudShell.
* From the GCP web console, stop the Dataflow streaming pipeline.

