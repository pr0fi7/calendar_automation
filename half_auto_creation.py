import os.path
import os
import requests
from icalendar import Calendar
import openai
import pytz
import pyperclip
from datetime import datetime, date, time, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())
openai.api_key = os.getenv("OPENAI_API_KEY")

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def return_whole_prompt(academic_schedule_formatted):
    prompt = f"""
    Given all the rules and the academic schedule below, and other comments from our conversation generate the best schedule for the upcoming week:
    # Academic Schedule:
    # {academic_schedule_formatted}
    """
    pyperclip.copy(prompt)

    print(prompt)

def format_schedule_events(events):
    """
    Formats a list of events into a string suitable for inclusion in the prompt.
    """
    event_str_list = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        summary = event.get('summary', 'No Title')
        event_str = f"Start: {start}, End: {end}, Activity: {summary}"
        event_str_list.append(event_str)
    return '\n'.join(event_str_list)


def get_academic_week(week=True):
    url = "https://cloud.timeedit.net/be_kuleuven/web/public/s.ics?sid=7&type=student&field=student.schedule.id&value=2F5F351118F21EEF9BF80230DF177777"
    response = requests.get(url)
    if response.status_code != 200:
        print("Failed to retrieve the academic schedule.")
        return []

    cal = Calendar.from_ical(response.content)
    academic_events = []

    # Set time zone to Europe/Brussels
    tz = pytz.timezone('Europe/Brussels')


    if week:
        today = datetime.now(tz) + timedelta(days=6)  # Adjust days as needed
        # Compute start_of_week and end_of_week
        start_of_week = datetime.combine((today - timedelta(days=today.weekday())).date(), time.min)
        start_of_week = tz.localize(start_of_week)

        end_of_week = datetime.combine(start_of_week.date() + timedelta(days=6), time.max)
        end_of_week = tz.localize(end_of_week)
    else:
        start_of_week = datetime.now()
        start_of_week = tz.localize(start_of_week)

        end_of_week = datetime.combine(start_of_week.date() + timedelta(days=6), time.max)
        end_of_week = tz.localize(end_of_week)

    for component in cal.walk():
        if component.name == "VEVENT":
            event_start = component.get('dtstart').dt
            event_end = component.get('dtend').dt

            # Ensure event_start and event_end are datetime objects with tzinfo
            if isinstance(event_start, datetime):
                if event_start.tzinfo is None:
                    event_start = tz.localize(event_start)
                else:
                    # Convert event_start to Europe/Brussels time zone
                    event_start = event_start.astimezone(tz)
            else:
                # event_start is a date object
                event_start = datetime.combine(event_start, time.min)
                event_start = tz.localize(event_start)

            if isinstance(event_end, datetime):
                if event_end.tzinfo is None:
                    event_end = tz.localize(event_end)
                else:
                    # Convert event_end to Europe/Brussels time zone
                    event_end = event_end.astimezone(tz)
            else:
                event_end = datetime.combine(event_end, time.min)
                event_end = tz.localize(event_end)

            if start_of_week <= event_start <= end_of_week:
                summary = str(component.get('summary'))
                academic_events.append({
                    'start': {'dateTime': event_start.isoformat()},
                    'end': {'dateTime': event_end.isoformat()},
                    'summary': summary
                })

    return academic_events

def text_to_schedule(generated_schedule_text):
    """
    Parses the generated schedule text and returns a list of events.
    Each event is a dictionary with 'start', 'end', 'summary'.
    """

    # Mapping of day names to weekday numbers
    days_of_week = {
        'Monday': 0,
        'Tuesday':1,
        'Wednesday':2,
        'Thursday':3,
        'Friday':4,
        'Saturday':5,
        'Sunday':6
    }

    timezone = pytz.timezone('Europe/Brussels')  # Set your time zone here

    today = datetime.now() + timedelta(days=6)  # Adjust days as needed
    start_of_week = today - timedelta(days=today.weekday())  # Monday

    events = []

    lines = generated_schedule_text.strip().split('\n')
    for line in lines:
        if not line.strip():
            continue

        line = line.strip()

        if "Structure, Behaviour and Sustainability of Materials" in line:
            line = line.replace("Structure, Behaviour and Sustainability of Materials", "Structure Behaviour and Sustainability of Materials")

        # Skip lines that do not match the expected format
        if len(line.split(',')) > 5:    
            print(f"Skipping line due to incorrect format: {line}")
            continue

        # Split line by commas
        parts = [part.strip() for part in line.split(',')]
        if len(parts) > 5:
            print(f"Skipping line due to incorrect format: {line}")
            continue

        if len(parts) == 5:
            day_str, start_time_str, end_time_str, activity, location = parts
        elif len(parts) == 4:
            day_str, start_time_str, end_time_str, activity = parts
            location = ''  # Default to empty string if location is not provided
        else:
            print(f"Skipping line due to incorrect format: {line}")
            continue

        # Clean up day string (remove asterisks, if any)
        day_str = day_str.strip('*').strip()

        # Get the date of the day
        weekday = days_of_week.get(day_str)
        if weekday is None:
            print(f"Unknown day: {day_str}")
            continue
        event_date = start_of_week + timedelta(days=weekday)

        # Parse start and end times
        try:
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time()
        except ValueError:
            print(f"Incorrect time format in line: {line}")
            continue

        start_datetime = datetime.combine(event_date.date(), start_time)
        end_datetime = datetime.combine(event_date.date(), end_time)

        # Handle cases where end time is past midnight
        if end_datetime <= start_datetime:
            end_datetime += timedelta(days=1)

        # Localize the datetime objects
        start_datetime = timezone.localize(start_datetime)
        end_datetime = timezone.localize(end_datetime)

        event = {
            'start': start_datetime,
            'end': end_datetime,
            'summary': activity,
            'location': location
            
        }

        events.append(event)

    return events

def delete_events_for_week(creds, week=True):
    """
    Deletes all events in the user's primary calendar for the next week.
    """
    service = build("calendar", "v3", credentials=creds)
    today = date.today()
    
    if week:
        # Calculate next week's Monday:
        # today.weekday() returns 0 for Monday, so if today is Monday, add 7 days.
        days_until_next_monday = (7 - today.weekday()) if today.weekday() != 0 else 7
        start_of_next_week = datetime.combine(today + timedelta(days=days_until_next_monday), time.min)
        # Next week's Sunday end-of-day:
        end_of_next_week = datetime.combine(start_of_next_week.date() + timedelta(days=6), time.max)
    else:
        # Use the current week (if needed)
        start_of_week = datetime.combine(today - timedelta(days=today.weekday()), time.min)
        end_of_week = datetime.combine(start_of_week.date() + timedelta(days=6), time.max)
    
    # Use the appropriate variables based on the chosen week.
    time_min = start_of_next_week.isoformat() + 'Z' if week else start_of_week.isoformat() + 'Z'
    time_max = end_of_next_week.isoformat() + 'Z' if week else end_of_week.isoformat() + 'Z'
    
    events_result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    
    if not events:
        print("No events to delete for the specified week.")
        return

    for event in events:
        try:
            service.events().delete(calendarId="primary", eventId=event['id']).execute()
            print(f"Deleted event: {event.get('summary', 'No Title')} on {event['start'].get('dateTime', event['start'].get('date'))}")
        except Exception as e:
            print(f"Failed to delete event: {event.get('summary', 'No Title')}. Error: {e}")

def insert_events(creds, events):
    """
    Inserts the events into Google Calendar with consistent color coding.
    """
    service = build("calendar", "v3", credentials=creds)

    # Define a color map for different activities
    color_map = {
        'Workout': '2',           # Lavender
        'Coding': '1',            # Blue
        'Climbing': '5',          # Yellow
        'French Class CVO': '7',  # Gray
        'Self-studying French': '8', # Gray
        'Guitar Learning': '4',   # Green
        'Self-studying Electronics': '6',  # Orange
        'Reading': '11',          # Red
        'Work': '11',   
        '3D Modeling': '2',       # Lavender
        'My Projects': '9',         # Cyan
        'Default': '10'           # Light Green
    }

    for event in events:
        activity = event['summary']
        location = event.get('location', '')
        color_id = color_map.get(activity, color_map['Default'])

        event_body = {
            'summary': activity,
            'start': {
                'dateTime': event['start'].isoformat(),
                'timeZone': 'Europe/Brussels',
            },
            'end': {
                'dateTime': event['end'].isoformat(),
                'timeZone': 'Europe/Brussels',
            },
            'colorId': color_id,
            'location': location
        }
        try:
            service.events().insert(calendarId='primary', body=event_body).execute()
            print(f"Inserted event: {activity} on {event['start']}")
        except Exception as e:
            print(f"Failed to insert event: {activity}. Error: {e}")



def adjust_schedule(events, creds):

    academic_schedule = get_academic_week(week=False)
    academic_schedule_formatted = format_schedule_events(academic_schedule)
    return_whole_prompt(academic_schedule_formatted)
    
    # Take input for the adapted schedule
    print("https://chatgpt.com/")
    adapted_schedule_text = input('Input yes if you have put the text in text.txt file:')

    if adapted_schedule_text.lower() == 'yes':
        with open("text2.txt", "r") as file:
            adapted_schedule_text = file.read()
    
    # Parse the input into a schedule
    events = text_to_schedule(adapted_schedule_text)
    
    # Delete existing events for the week in Google Calendar
    delete_events_for_week(creds)
    
    # Insert the new events into Google Calendar
    insert_events(creds, events)
    print("Schedule successfully inserted into Google Calendar.")


def main():
    """Generates a schedule based on rules, personal schedule, and academic schedule, and inserts it into Google Calendar."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    # Fetch the academic schedule
    academic_schedule = get_academic_week()

    # Format and print the schedule prompt
    academic_schedule_formatted = format_schedule_events(academic_schedule)
    return_whole_prompt(academic_schedule_formatted)
    
    # Take input for the adapted schedule
    print("https://chatgpt.com/")
    adapted_schedule_text = input('Input yes if you have put the text in text.txt file:')

    if adapted_schedule_text.lower() == 'yes':
        with open("text.txt", "r") as file:
            adapted_schedule_text = file.read()
    
    # Parse the input into a schedule
    events = text_to_schedule(adapted_schedule_text)
    
    # Delete existing events for the week in Google Calendar
    delete_events_for_week(creds)
    
    # Insert the new events into Google Calendar
    insert_events(creds, events)
    print("Schedule successfully inserted into Google Calendar.")

if __name__ == "__main__":
    main()
