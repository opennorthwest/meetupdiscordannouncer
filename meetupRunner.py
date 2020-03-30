import requests
import os, sys
import datetime, time
from discord_webhook import DiscordWebhook


def get_events(group):
  # api-endpoint
  URL = "https://api.meetup.com/%s/events?&sign=true&photo-host=public&page=10"%(group)
  # sending get request and saving the response as response object
  r = requests.get(url = URL)
  return r.json()

def build_message(event):
  message = "Join us today at %s for %s.\n %s people attending so far! Sign up: <%s>"%(event['local_time'], event['name'], event['yes_rsvp_count'], event['link'])
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

messages = []
for event in events:
  #event_date = datetime.strptime(event.local_date, '%Y-%m-%d')
  event_date = datetime.datetime(*(time.strptime(event['local_date'], '%Y-%m-%d')[0:6]))
  if event_date.date() == now.date():
    messages.append(build_message(event))

for message in messages:
	print(message)
	publish_message(discord_url,message)

