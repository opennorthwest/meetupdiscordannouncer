import os
import sys
import calendar
import yaml
import requests
import logging
import pytz
import configargparse
from discord_webhook import DiscordWebhook
from pytz import timezone
from icalendar import Calendar
from datetime import datetime
from zoneinfo import ZoneInfo
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    from dateutil import tz
    ZoneInfo = tz.gettz  # zoneinfo substitute for older Python

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Argument parsing
parser = configargparse.ArgumentParser(
    description="Meetup event reminder bot"
)

parser.add_argument(
    "--config", is_config_file=True, help="Path to configuration file"
)
parser.add_argument(
    "--debug", action="store_true", help="Enable debug mode"
)
parser.add_argument(
    "--dry-run", action="store_true", help="Run in dry run mode without sending messages"
)

args = parser.parse_args()

# Set logging level based on debug flag
if args.debug:
    logger.setLevel(logging.DEBUG)
    logger.debug("Debug mode enabled.")

# Load configuration with environment variable substitution
def load_config():
    try:
        with open(args.config or "config.yaml", "r") as file:
            raw_config = file.read()
            # Expand environment variables
            expanded_config = os.path.expandvars(raw_config)
            config = yaml.safe_load(expanded_config)
            logger.debug(f"Loaded config with env vars: {config}")
            return config
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

config = load_config()

def validate_config():
    if 'discord' not in config or 'webhook' not in config['discord']:
        logger.error("Missing Discord webhook in configuration.")
        sys.exit(1)
    if 'meetup' not in config or 'ical' not in config['meetup']:
        logger.error("Missing Meetup ical in configuration.")
        sys.exit(1)
    if config['discord'].get('summary', {}).get('enabled', False) and 'webhook' not in config['discord']['summary']:
        logger.error("Missing summary Discord webhook in configuration while summary is enabled.")
        sys.exit(1)

validate_config()

def get_events_from_ical(url):
    try:
        res = requests.get(url)
        res.raise_for_status()
        cal = Calendar.from_ical(res.content)
    except Exception as e:
        logger.error(f"Failed to load or parse iCal feed: {e}")
        return []

    events = []
    default_tz = ZoneInfo(config['timezone'])

    for component in cal.walk('VEVENT'):
        try:
            status = component.get('STATUS')
            if status and status != 'CONFIRMED':
                continue

            summary = str(component.get('SUMMARY'))
            start = component.get('DTSTART').dt
            url = str(component.get('URL'))

            if isinstance(start, datetime):
                if start.tzinfo is None:
                    start = start.replace(tzinfo=default_tz)
                else:
                    start = start.astimezone(default_tz)
            else:
                # Handle all-day events
                start = datetime.combine(start, datetime.min.time(), tzinfo=default_tz)

            if start >= datetime.now(tz=default_tz):
                events.append({
                    'name': summary,
                    'time': start,
                    'url': url
                })
        except Exception as e:
            logger.warning(f"Failed to parse event: {e}")

    events.sort(key=lambda e: e['time'])
    return events


def build_weekly_msg(event):
    event_date = event['time']
    day_name = calendar.day_name[event_date.weekday()]
    date_str = event_date.strftime("%B %d")  # e.g., "March 21"
    time_str = event_date.strftime("%I:%M %p")  # e.g., "06:00 PM"

    msg = (
        f"Don't forget to sign up for **{event['name']}** on {day_name}, {date_str} at {time_str}.\n"
        f"RSVP here: <{event['url']}>"
    )
    logger.debug(f"Weekly message: {msg}")
    return msg

def build_reminder_msg(event):
    time_str = event['time'].strftime("%I:%M %p")
    msg = (
        f"Join us today at {time_str} for **{event['name']}**.\n"
        f"Sign up: <{event['url']}>"
    )
    logger.debug(f"Reminder message: {msg}")
    return msg

def publish_message(discord_webhook, msg, thread_id=None, dry_run=False):
    if dry_run:
        logger.info(f"[DRY RUN] {msg}")
    else:
        try:
            webhook = DiscordWebhook(url=discord_webhook, content=msg, thread_id=thread_id)
            webhook.execute()
            logger.info(f"Published message: {msg}")
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")

def is_summary_day():
    today = calendar.day_name[datetime.today().weekday()].lower()
    logger.debug(f"Checking summary day: Today is {today}")
    return today == config['discord']['summary']['daily']

def get_event_config(event_name):
    """
    Find the best matching event configuration. If no match is found, use event.default.
    """
    for event_pattern, event_info in config['events'].items():
        if event_pattern != "default" and event_pattern in event_name:
            return event_info

    logger.debug(f"No specific match for event '{event_name}', using defaults.")
    return config['events'].get("default", {})

def main():
    logger.info("Starting event processing script...")
    discord_webhook = config['discord']['webhook']
    group = config['meetup']['ical']
    summary_webhook = config['discord']['summary'].get('webhook')
    tz = ZoneInfo(config['timezone'])
    events = get_events_from_ical(group)
    now = datetime.now(tz).replace(hour=1)
    summary_messages = []
    
    if not events:
        logger.warning("No events found.")

    for event in events:
        try:
            event_date = event['time']
            event_config = get_event_config(event['name'])

            logger.debug(f"Processing event: {event['name']} on {event_date} with config: {event_config}")

            thread_id = event_config.get('thread_id')
            days_difference = (event_date - now).days
            logger.debug(f"Timing: Today is {now} event_date is {event_date}, Date difference is {days_difference}")
            # Gather the events for the week
            if days_difference <= 7:
                msg = build_weekly_msg(event)
                summary_messages.append(msg)
                # Weekly Reminder
                if days_difference == 7:
                    publish_message(discord_webhook, msg, thread_id, args.dry_run)

            # Event Day Reminder
            if event_config.get('reminder', False) and days_difference == 0:
                msg = build_reminder_msg(event)
                logger.debug(msg)
                publish_message(discord_webhook, msg, thread_id, args.dry_run)

        except Exception as e:
            logger.error(f"Error processing event {event}: {e}")

    # Summary Message
    if is_summary_day() and config['discord']['summary']['enabled']:
        summary = "Upcoming Events This Week:\n" + "\n".join(summary_messages)
        publish_message(summary_webhook, summary, None, args.dry_run)

    logger.info("Event processing complete.")

if __name__ == "__main__":
    main()
