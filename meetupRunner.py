import datetime
import os
import sys
import time
import calendar
import yaml
import requests
from discord_webhook import DiscordWebhook

# Load configuration
def load_config():
    with open("config.yaml", "r") as file:
        return yaml.safe_load(file)

config = load_config()

def validate_config():
    if 'discord' not in config or 'webhook' not in config['discord']:
        print("Missing Discord webhook in configuration.")
        sys.exit(1)
    if 'meetup' not in config or 'group' not in config['meetup']:
        print("Missing Meetup group in configuration.")
        sys.exit(1)

validate_config()

def get_events(group):
    url = f"https://api.meetup.com/{group}/events?&sign=true&photo-host=public&page=10"
    res = requests.get(url=url)
    return res.json()

def build_weekly_msg(event, event_date):
    return f"Don't forget to sign up for {event['name']} on {calendar.day_name[event_date.weekday()]}.\nRSVP here: <{event['link']}>"

def build_reminder_msg(event):
    return f"Join us today at {event['local_time']} for {event['name']}.\n{event['yes_rsvp_count']} people attending so far! Sign up: <{event['link']}>"

def publish_message(discord_url, msg, thread_id=None, dry_run=False):
    if dry_run:
        print(f"[DRY RUN] {msg}")
    else:
        webhook = DiscordWebhook(url=discord_url, content=msg, thread_id=thread_id)
        webhook.execute()

def is_summary_day():
    return calendar.day_name[datetime.datetime.today().weekday()].lower() == config['discord']['summary']['daily']

def main(dry_run=False):
    discord_url = config['discord']['webhook']
    group = config['meetup']['group']
    
    events = get_events(group)
    now = datetime.datetime.today()
    summary_messages = []
    
    for event in events:
        event_date = datetime.datetime.strptime(event['local_date'], '%Y-%m-%d')
        
        for event_pattern, event_info in config['events'].items():
            if event_pattern in event['name']:
                thread_id = event_info.get('thread_id')
                if event_date.date() <= now.date() + datetime.timedelta(days=7):
                    msg = build_weekly_msg(event, event_date)
                    summary_messages.append(msg)
                    publish_message(discord_url, msg, thread_id, dry_run)
                
                if event_info.get('reminder', False) and event_date.date() == now.date():
                    msg = build_reminder_msg(event)
                    publish_message(discord_url, msg, thread_id, dry_run)
    
    if is_summary_day() and config['discord']['summary']['enabled']:
        summary = "Upcoming Events This Week:\n" + "\n".join(summary_messages)
        publish_message(discord_url, summary, None, dry_run)

if __name__ == "__main__":
    dry_run_mode = '--dry-run' in sys.argv
    main(dry_run_mode)
