#!/usr/bin/env python3

# Copyright 2016 Google Inc.
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

import time
import pytz
import logging
import argparse
import datetime
import google.cloud.pubsub_v1 as pubsub # Use v1 of the API
import google.cloud.bigquery as bq

TIME_FORMAT = '%Y-%m-%d %H:%M:%S %Z'
RFC3339_TIME_FORMAT = '%Y-%m-%dT%H:%M:%S-00:00'

publish_futures = []

def check_futures():
   logging.info('Checking..')
   for f in publish_futures:
      print('result', f.result())
   logging.info('Check Done')

def publish(publisher, topics, allevents, notify_time):
   if notify_time is None:
      return
   
   timestamp = notify_time.strftime(RFC3339_TIME_FORMAT)
   for key in topics:  # 'departed', 'arrived', etc.
      topic = topics[key]
      events = allevents[key]
      # the client automatically batches
      logging.info('Publishing {} {} till {}'.format(len(events), key, timestamp))
      for event_data in events:
          print('DDD', event_data)
          # Need to encode to utf-8 byte array
          future = publisher.publish(topic, event_data.encode(), EventTimeStamp=timestamp)
          publish_futures.append(future)

def notify(publisher, topics, rows, simStartTime, programStart, speedFactor):
   print('XXX notify', simStartTime, programStart, speedFactor)
   # sleep computation
   def compute_sleep_secs(notify_time):
        print('XXX csc notify_time', notify_time)
        time_elapsed = (datetime.datetime.utcnow() - programStart).total_seconds()
        print('XXX csc time_elapsed', time_elapsed)
        sim_time_elapsed = (notify_time - simStartTime).total_seconds() / speedFactor
        print('XXX csc sim_time_elapsed', sim_time_elapsed)
        to_sleep_secs = sim_time_elapsed - time_elapsed
        print('XXX csc to_sleep_secs', to_sleep_secs)
        return to_sleep_secs

   tonotify = {}
   for key in topics:
     tonotify[key] = list()
   tonotify_time = None

   for row in rows:
       event_type, notify_time, event_data = row

       # how much time should we sleep?
       if compute_sleep_secs(notify_time) > 1:
          # notify the accumulated tonotify
          publish(publisher, topics, tonotify, tonotify_time)
          for key in topics:
             tonotify[key] = list()

          # recompute sleep, since notification takes a while
          to_sleep_secs = compute_sleep_secs(notify_time)
          if to_sleep_secs > 0:
             logging.info('Sleeping {} seconds'.format(to_sleep_secs))
             time.sleep(to_sleep_secs)
       tonotify[event_type].append(event_data)
       tonotify_time = notify_time

   # left-over records; notify again
   publish(publisher, topics, tonotify, tonotify_time)


if __name__ == '__main__':
   parser = argparse.ArgumentParser(description='Send simulated flight events to Cloud Pub/Sub')
   parser.add_argument('--startTime', help='Example: 2015-05-01 00:00:00 UTC', required=True)
   parser.add_argument('--endTime', help='Example: 2015-05-03 00:00:00 UTC', required=True)
   parser.add_argument('--project', help='your project id, to create pubsub topic', required=True)
   parser.add_argument('--speedFactor', help='Example: 60 implies 1 hour of data sent to Cloud Pub/Sub in 1 minute', required=True, type=float)
   parser.add_argument('--jitter', help='type of jitter to add: None, uniform, exp  are the three options', default='None')
   parser.add_argument('--dataset', help='Dataset where flights events table exists',required=True)

   # set up BigQuery bqclient
   logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
   args = parser.parse_args()
   dataset = args.dataset
   bqclient = bq.Client(args.project)
   bqclient.get_table(f'{dataset}.flights_simevents')  # throws exception on failure

   # jitter?
   if args.jitter == 'exp':
      jitter = 'CAST (-LN(RAND()*0.99 + 0.01)*30 + 90.5 AS INT64)'
   elif args.jitter == 'uniform':
      jitter = 'CAST(90.5 + RAND()*30 AS INT64)'
   else:
      jitter = '0'


   # run the query to pull simulated events
   querystr = f"""
SELECT
  EVENT_TYPE,
  TIMESTAMP_ADD(EVENT_TIME, INTERVAL @jitter SECOND) AS NOTIFY_TIME,
  EVENT_DATA
FROM
  {dataset}.flights_simevents
WHERE
  EVENT_TIME >= @startTime
  AND EVENT_TIME < @endTime
ORDER BY
  EVENT_TIME ASC
"""
   print('XXX querystr', querystr)
   job_config = bq.QueryJobConfig(
       query_parameters=[
           bq.ScalarQueryParameter("jitter", "INT64", jitter),
           bq.ScalarQueryParameter("startTime", "TIMESTAMP", args.startTime),
           bq.ScalarQueryParameter("endTime", "TIMESTAMP", args.endTime),
       ]
   )
   rows = bqclient.query(querystr, job_config=job_config)

   # create one Pub/Sub notification topic for each type of event
   publisher = pubsub.PublisherClient()
   topics = {}
   for event_type in ['wheelsoff', 'arrived', 'departed']:
       topics[event_type] = publisher.topic_path(args.project, event_type)
       try:
           publisher.get_topic(topic=topics[event_type])
           logging.info("Already exists: {}".format(topics[event_type]))
       except:
           logging.info("Creating {}".format(topics[event_type]))
           publisher.create_topic(name=topics[event_type])


   # notify about each row in the dataset
   programStartTime = datetime.datetime.utcnow()
   simStartTime = datetime.datetime.strptime(args.startTime, TIME_FORMAT).replace(tzinfo=pytz.UTC)
   logging.info('Simulation start time is {}'.format(simStartTime))
   notify(publisher, topics, rows, simStartTime, programStartTime, args.speedFactor)
   check_futures()
