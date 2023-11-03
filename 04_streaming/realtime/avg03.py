#!/usr/bin/env python3

# Copyright 2021 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import apache_beam as beam
import logging
import json
import numpy as np
import datetime

DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S'
RFC3339_TIME_FORMAT = '%Y-%m-%dT%H:%M:%S-00:00'


def compute_stats(airport, events):
    arrived = [event['ARR_DELAY'] for event in events if event['EVENT_TYPE'] == 'arrived']
    avg_arr_delay = float(np.mean(arrived)) if len(arrived) > 0 else None

    departed = [event['DEP_DELAY'] for event in events if event['EVENT_TYPE'] == 'departed']
    avg_dep_delay = float(np.mean(departed)) if len(departed) > 0 else None

    num_flights = len(events)
    start_time = min([event['EVENT_TIME'] for event in events])
    latest_time = max([event['EVENT_TIME'] for event in events])

    logging.info(f'compute_stats: {num_flights}, {start_time}, {latest_time}')

    return {
        'AIRPORT': airport,
        'AVG_ARR_DELAY': avg_arr_delay,
        'AVG_DEP_DELAY': avg_dep_delay,
        'NUM_FLIGHTS': num_flights,
        'START_TIME': start_time,
        'END_TIME': latest_time
    }

def log_before_groupby(element):
    logging.info(f"Before GroupBy: {element}")
    return element

def log_after_groupby(element):
    logging.info(f"After GroupBy: {element}")
    return element

def by_airport(event):
    logging.info(f"by_airport type={event['EVENT_TYPE']}")
    if event['EVENT_TYPE'] == 'departed':
        return event['ORIGIN'], event
    else:
        return event['DEST'], event

# ウィンドウの内容をログに出力するカスタムDoFnクラス
class LogWindowContents(beam.DoFn):
    def process(self, element, window=beam.DoFn.WindowParam):
        logging.info(f"Window: {window.start.to_utc_datetime()} - {window.end.to_utc_datetime()}, Element: {element}")
        yield element

def run(project, bucket, region, dataset):
    argv = [
        '--project={0}'.format(project),
        '--job_name=ch04avgdelay10',
        '--streaming',
        '--save_main_session',
        '--staging_location=gs://{0}/flights/staging/'.format(bucket),
        '--temp_location=gs://{0}/flights/temp/'.format(bucket),
        '--autoscaling_algorithm=THROUGHPUT_BASED',
        '--max_num_workers=8',
        '--region={}'.format(region),
        '--runner=DataflowRunner'
    ]

    import logging
    logging.getLogger().setLevel(logging.INFO)

    def log_and_parse_event(msg):
        event_timestamp = msg.attributes['EventTimeStamp']
        logging.info(f'Processing event: {event_timestamp}, {msg.data}')
        event = json.loads(msg.data)
        event_time = datetime.datetime.strptime(event_timestamp, RFC3339_TIME_FORMAT ) # タイムスタンプの形式に応じて変更
        return beam.window.TimestampedValue(event, event_time.timestamp())

    with beam.Pipeline(argv=argv) as pipeline:
        events = {}

        for event_name in ['arrived', 'departed']:
            topic_name = "projects/{}/topics/{}".format(project, event_name)

            events[event_name] = (pipeline
                                  | f'read:{event_name}' >> beam.io.ReadFromPubSub(topic=topic_name, with_attributes=True)
                                  | f'parse:{event_name}' >> beam.Map(log_and_parse_event)
                                  )

        all_events = (events['arrived'], events['departed']) | beam.Flatten()

        windowed_events = (all_events
                       | 'byairport' >> beam.Map(by_airport)
                       | 'window' >> beam.WindowInto(beam.window.SlidingWindows(60 * 60 * 2, 10 * 60))
                       | 'Log Window Contents' >> beam.ParDo(LogWindowContents())  # この行を追加
                      )

        stats = (windowed_events
                | 'Log Before GroupBy' >> beam.Map(log_before_groupby)
                | 'group' >> beam.GroupByKey()
                | 'Log After GroupBy' >> beam.Map(log_after_groupby)
                | 'stats' >> beam.Map(lambda x: compute_stats(x[0], x[1]))
                )

       # stats = (all_events
       #          | 'byairport' >> beam.Map(by_airport)
       #          # Change windows size 2 hours, every 10 minutes
       #          | 'window' >> beam.WindowInto(beam.window.SlidingWindows(60 * 60 * 2, 10 * 60))
       #          | 'group' >> beam.GroupByKey()
       #          | 'stats' >> beam.Map(lambda x: compute_stats(x[0], x[1]))
       # )

        stats_schema = ','.join(['AIRPORT:string,AVG_ARR_DELAY:float,AVG_DEP_DELAY:float',
                                 'NUM_FLIGHTS:int64,START_TIME:timestamp,END_TIME:timestamp'])
        (stats
         | 'bqout' >> beam.io.WriteToBigQuery(
                    f'{dataset}.streaming_delays6', schema=stats_schema,
                    create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED
                )
         )


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run pipeline on the cloud')
    parser.add_argument('-p', '--project', help='Unique project ID', required=True)
    parser.add_argument('-b', '--bucket', help='Bucket where gs://BUCKET/flights/airports/airports.csv.gz exists',
                        required=True)
    parser.add_argument('-r', '--region',
                        help='Region in which to run the Dataflow job. Choose the same region as your bucket.',
                        required=True)
    parser.add_argument('-d', '--dataset', help='Dataset where output is written.',
                        required=True)

    args = vars(parser.parse_args())

    run(project=args['project'], bucket=args['bucket'], region=args['region'], dataset=args['dataset'])
