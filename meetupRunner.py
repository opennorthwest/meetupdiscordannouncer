import datetime
import os
import sys
import time
import calendar

import requests
from discord_webhook import DiscordWebhook


def get_events(group):
  # api-endpoint
  URL = "https://api.meetup.com/%s/events?&sign=true&photo-host=public&page=10" % (group)
  # sending get request and saving the response as response object
  r = requests.get(url=URL)
  return r.json()


def build_weekly_msg(event, event_date):
  message = 'Don\'t forget to sign up for {name} on {weekday}\nRSVP here: <{link}>'.format(name=event['name'], link=event['link'], weekday=calendar.day_name[event_date.weekday()])
  return message


def build_message(event):
  message = "Join us today at %s for %s.\n %s people attending so far! Sign up: <%s>" % (event['local_time'], event['name'], event['yes_rsvp_count'], event['link'])
  return message


def publish_message(discord_url, msg):
  webhook = DiscordWebhook(url=discord_url, content=message)
  response = webhook.execute()


discord_url = os.environ.get('DISCORD_URL')
group = os.environ.get('MEETUP_GROUP')
if not discord_url and group:
  print('Missing a required environment variable')
  sys.exit(1)
events = get_events(group)

now = datetime.datetime.today()
sunday = True if now.weekday() == 6 else False
messages = []
for event in events:
  event_date = datetime.datetime(*(time.strptime(event['local_date'], '%Y-%m-%d')[0:6]))
  if event_date.date() <= now.date() + datetime.timedelta(days=7 if sunday else 1):
    messages.append(build_weekly_msg(event, event_date) if sunday else build_message(event))

for message in messages:
  print(message)
  publish_message(discord_url, message)
