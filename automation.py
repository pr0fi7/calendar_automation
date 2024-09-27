import datetime
import os.path
import os
import requests
from icalendar import Calendar
import openai
import pytz
import re

import matplotlib.pyplot as plt
from matplotlib.table import Table

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())
openai.api_key = os.getenv("OPENAI_API_KEY")

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Simplified and clarified rules for AI understanding
rules = '''
this rules are very very important for you to follow while compiling the schedule strictly follow all of them or you will be punished:
- Ensure that exactly 2 days have a Work block strictly from 9:00 to 17:00.
- Schedule exactly 3 climbing training sessions a week, each lasting 3 hours. One session must be after the French class on Saturday, from 15:15 to 18:15 and other 2 should allow sufficient rest between sessions depending on the week. Training sessions besides the one on Saturday should be scheduled in the evening.(e.g., 18:00-21:00)
- Do not miss any French classes at CVO; they always take place on Thursday 18:15 - 21:15 and Saturday 9:00 - 15:15.
- Do not miss any lessons which starts with "T1". 
- On Sundays, always put 8:00 - 18:00 Free Time.
- Start each day with a 30-minute Workout
- End each day should end with: (22:00, 22:45, Guitar Learning; 22:45, 00:30, Self-studying Electronics; 00:30, 01:00, Reading) if next day starts at 8:30, else (21:30, 22:15, Guitar Learning; 22:15, 23:45, Self-studying Electronics; 23:45, 00:15, Reading) if next day starts at 8:00. If the next day starts at 9:00, then end the day before with (22:00, 22:45, Guitar Learning; 22:45, 00:30, Self-studying Electronics; 00:30, 01:00, Reading).
- Include 1 hour block for 'My Projects' as one block each day and at least one 4-hour block for 'My Projects' once a week(but not on weekends) . 
- Once you are done with that and everything else is set, if you have free blocks of time, fill them with Learning Coding activities, Learn 3d Modeling activities, Self-studying French ensure that they are well distributed throughout the week there should not be free time except on Sundays.
- Combine consecutive activities of the same type into a single time block (e.g., "9:00-11:00 Workout" instead of "9:00-10:00 Workout" and "10:00-11:00 Workout").
- Use the following names for activities: Work, Workout, Coding, Climbing, French Class CVO, Self-studying French, Guitar Learning, Self-studying Electronics, Reading, Sleep, 3d Modeling.
- Do not include any time for lunch or dinner act as they don't exist.
- Do not include any time for commuting. Assume that all activities take place at home.
- Do not include any time for breaks between activities. It should not have any empty time slots.
- Format your answer in 24-hour time format (e.g., 09:00, 13:30).
- Take into account only activities of the current week.    
'''

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

# def get_my_current_week(creds):
#     today = datetime.datetime.now()
#     start_of_week = today - datetime.timedelta(days=today.weekday())  # Monday
#     end_of_week = start_of_week + datetime.timedelta(days=7)  # Next Monday
#     service = build("calendar", "v3", credentials=creds)
#     events_result = (
#         service.events()
#         .list(
#             calendarId="primary",
#             timeMin=start_of_week.isoformat() + "Z",
#             timeMax=end_of_week.isoformat() + "Z",
#             singleEvents=True,
#             orderBy="startTime",
#         )
#         .execute()
#     )
#     events = events_result.get("items", [])
#     return events

def get_academic_week():
    url = "https://cloud.timeedit.net/be_kuleuven/web/public/s.ics?sid=7&type=student&field=student.schedule.id&value=2F5F351118F21EEF9BF80230DF177777"
    response = requests.get(url)
    if response.status_code != 200:
        print("Failed to retrieve the academic schedule.")
        return []

    cal = Calendar.from_ical(response.content)
    academic_events = []

    # Get today's date without time
    today = datetime.date.today()

    # Set start of the week to Monday 00:00
    start_of_week = datetime.datetime.combine(today - datetime.timedelta(days=today.weekday()), datetime.time.min)

    # Set end of the week to next Monday 00:00
    end_of_week = datetime.datetime.combine(start_of_week.date() + datetime.timedelta(days=6), datetime.time.max)


    for component in cal.walk():
        if component.name == "VEVENT":
            event_start = component.get('dtstart').dt
            event_end = component.get('dtend').dt

            # Ensure datetime objects are timezone-aware
            if isinstance(event_start, datetime.datetime):
                event_start = event_start.replace(tzinfo=None)
            else:
                event_start = datetime.datetime.combine(event_start, datetime.time.min)

            if isinstance(event_end, datetime.datetime):
                event_end = event_end.replace(tzinfo=None)
            else:
                event_end = datetime.datetime.combine(event_end, datetime.time.min)

            if start_of_week <= event_start <= end_of_week:
                summary = str(component.get('summary'))
                academic_events.append({
                    'start': {'dateTime': event_start.isoformat()},
                    'end': {'dateTime': event_end.isoformat()},
                    'summary': summary
                })

    return academic_events

def adapt_the_schedule(academic_schedule, rules, message=None, previous_schedules=None):
    # personal_schedule_formatted = format_schedule_events(personal_schedule)
    academic_schedule_formatted = format_schedule_events(academic_schedule)

    conversation = []
    conversation.append({
        "role": "system",
        "content": (
            f"You are the best time management assistant in the world. "
            f"Given the following rules which you need to follow while compiling the schedule: {rules}\n\n"
            f"Academic Schedule:\n{academic_schedule_formatted}\n\n"
            "Provide me with the best schedule for the upcoming week.\n\n"
            "**Important Instructions:**\n"
            "- Do not include any introductory or concluding text.\n"
            "- Output the schedule in the exact format: Day, Start Time, End Time, Activity.\n"
            "- Use one line per activity.\n"
            "- Do not use any markdown or special formatting.\n"
            "- Ensure that day names are spelled correctly (e.g., Monday, Tuesday).\n"
            "Example:\nMonday, 09:00, 10:00, Workout\nTuesday, 10:00, 12:00, Coding\n"
            "provide answer as a simple text don't use any code to create it"

        )
    })



    if previous_schedules:
        for schedule in previous_schedules:
            conversation.append({"role": "assistant", "content": schedule})
    if message:
        conversation.append({"role": "user", "content": message})


    conversation.append({"role": "system", "content": "Be very strict with the rules and ensure that the schedule is perfect and complies with all requirements. If you need to make any changes, provide detailed feedback of what to change. Otherwise, only type 'good' to finish."})

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=conversation,
        
    )

    answer = response.choices[0].message.content.strip()


    print(f"Generated Schedule:\n{answer}")
    return answer


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

    today = datetime.datetime.now()
    start_of_week = today - datetime.timedelta(days=today.weekday())  # Monday

    events = []

    lines = generated_schedule_text.strip().split('\n')
    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue

        # Remove any unwanted characters from the line
        line = line.strip()

        # Skip lines that do not match the expected format
        if len(line.split(',')) != 4:
            print(f"Skipping line due to incorrect format: {line}")
            continue

        # Split line by commas
        parts = [part.strip() for part in line.split(',')]
        if len(parts) != 4:
            print(f"Skipping line due to incorrect format: {line}")
            continue
        day_str, start_time_str, end_time_str, activity = parts

        # Clean up day string (remove asterisks, if any)
        day_str = day_str.strip('*').strip()

        # Get the date of the day
        weekday = days_of_week.get(day_str)
        if weekday is None:
            print(f"Unknown day: {day_str}")
            continue
        event_date = start_of_week + datetime.timedelta(days=weekday)

        # Parse start and end times
        try:
            start_time = datetime.datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.datetime.strptime(end_time_str, '%H:%M').time()
        except ValueError:
            print(f"Incorrect time format in line: {line}")
            continue

        start_datetime = datetime.datetime.combine(event_date.date(), start_time)
        end_datetime = datetime.datetime.combine(event_date.date(), end_time)

        # Handle cases where end time is past midnight
        if end_datetime <= start_datetime:
            end_datetime += datetime.timedelta(days=1)

        # Localize the datetime objects
        start_datetime = timezone.localize(start_datetime)
        end_datetime = timezone.localize(end_datetime)

        event = {
            'start': start_datetime,
            'end': end_datetime,
            'summary': activity
        }

        events.append(event)

    return events


def display_schedule_as_table(schedule_text):
    """
    Displays a text schedule in a table format using matplotlib, separating different weekdays and improving readability.
    """
    # Split the input text into lines
    lines = schedule_text.strip().split('\n')

    # Extract headers and data
    headers = ["Day", "Start Time", "End Time", "Activity"]
    table_data = []
    previous_day = None
    
    for line in lines:
        if line.strip():  # Ignore empty lines
            parts = line.split(', ')
            if len(parts) == 4:
                current_day = parts[0]
                if current_day != previous_day:
                    # Insert a separator row when the day changes
                    if previous_day is not None:
                        table_data.append(['', '', '', ''])  # Empty row for separation
                    previous_day = current_day
                table_data.append(parts)

    # Create figure and axis
    fig, ax = plt.subplots(figsize=(8, len(table_data) * 0.5))  # Adjust height based on number of rows

    # Hide the axes
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)
    ax.set_frame_on(False)

    # Create the table
    table = Table(ax, bbox=[0, 0, 1, 1])

    # Add table header
    col_widths = [0.2, 0.2, 0.2, 0.4]  # Set column widths
    for i, header in enumerate(headers):
        table.add_cell(0, i, width=col_widths[i], height=0.5, text=header, loc='center', facecolor='lightgray')

    # Add table rows with alternating background for readability
    for row_idx, row in enumerate(table_data):
        if row[0] != '':  # If it's a non-empty row, meaning a valid event
            background_color = 'lightyellow' if row_idx % 2 == 0 else 'lightcyan'
        else:
            background_color = 'white'  # Separator rows
        for col_idx, cell_value in enumerate(row):
            if col_idx == 0:  # Highlight the day column
                table.add_cell(row_idx + 1, col_idx, width=col_widths[col_idx], height=0.5, text=cell_value, loc='center', facecolor=background_color,)
            else:
                table.add_cell(row_idx + 1, col_idx, width=col_widths[col_idx], height=0.5, text=cell_value, loc='center', facecolor=background_color)

    # Add the table to the axis
    ax.add_table(table)

    # Set limits to fit the table
    ax.set_xlim(0, 1)
    ax.set_ylim(0, len(table_data) + 1)

    # Display the plot
    plt.tight_layout()
    plt.show()
    plt.waitforbuttonpress()

def delete_events_for_week(creds):
    """
    Deletes all events in the user's primary calendar for the current week.
    """
    service = build("calendar", "v3", credentials=creds)
    # Get today's date without time
    today = datetime.date.today()

    # Set start of the week to Monday 00:00
    start_of_week = datetime.datetime.combine(today - datetime.timedelta(days=today.weekday()), datetime.time.min)

    # Set end of the week to next Monday 00:00
    end_of_week = datetime.datetime.combine(start_of_week.date() + datetime.timedelta(days=7), datetime.time.max)

    events_result = service.events().list(
        calendarId="primary",
        timeMin=start_of_week.isoformat() + 'Z',
        timeMax=end_of_week.isoformat() + 'Z',
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])

    if not events:
        print("No events to delete for the current week.")
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
        'Free Time': '9',         # Cyan
        'Sleep': '3',             # Purple
        'Default': '10'           # Light Green
    }

    for event in events:
        activity = event['summary']
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
            'colorId': color_id
        }
        try:
            service.events().insert(calendarId='primary', body=event_body).execute()
            print(f"Inserted event: {activity} on {event['start']}")
        except Exception as e:
            print(f"Failed to insert event: {activity}. Error: {e}")

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

    try:
        # Get personal schedule
        # personal_schedule = get_my_current_week(creds)
        # Get academic schedule
        academic_schedule = get_academic_week()
        # Generate adapted schedule
        adapted_schedule_text = adapt_the_schedule(academic_schedule, rules)
        # display_schedule_as_table(adapted_schedule_text)

        previous_schedules = []
        previous_schedules.append(adapted_schedule_text)

        while True:
            message = input("Do you like the proposed schedule? If not, please provide feedback (or type 'yes' if you like it, or write a feedback if you don't and want to change something): ")
            if message.lower() == "yes":
                break
            elif message:
                adapted_schedule_text = adapt_the_schedule(academic_schedule, rules, message, previous_schedules)
                previous_schedules.append(adapted_schedule_text)
            else:
                print("Please provide feedback, type 'yes' to accept, or 'exit' to cancel.")

        # Parse adapted schedule into events
        events = text_to_schedule(adapted_schedule_text)

        # Delete existing events for the week
        delete_events_for_week(creds)

        # Insert events into Google Calendar with color coding
        insert_events(creds, events)
        print("Schedule successfully inserted into Google Calendar.")
    except HttpError as error:
        print(f"An error occurred: {error}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
