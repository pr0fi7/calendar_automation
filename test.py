# import requests
# from icalendar import Calendar
# import datetime

# def get_academic_week():
#     url = "https://cloud.timeedit.net/be_kuleuven/web/public/s.ics?sid=7&type=student&field=student.schedule.id&value=2F5F351118F21EEF9BF80230DF177777"
#     response = requests.get(url)
#     if response.status_code != 200:
#         print("Failed to retrieve the academic schedule.")
#         return []

#     cal = Calendar.from_ical(response.content)
#     academic_events = []

#     today = datetime.datetime.now()
#     start_of_week = today - datetime.timedelta(days=today.weekday())  # Monday
#     end_of_week = start_of_week + datetime.timedelta(days=7)

#     for component in cal.walk():
#         if component.name == "VEVENT":
#             event_start = component.get('dtstart').dt
#             event_end = component.get('dtend').dt

#             # Ensure datetime objects are timezone-aware
#             if isinstance(event_start, datetime.datetime):
#                 event_start = event_start.replace(tzinfo=None)
#             else:
#                 event_start = datetime.datetime.combine(event_start, datetime.time.min)

#             if isinstance(event_end, datetime.datetime):
#                 event_end = event_end.replace(tzinfo=None)
#             else:
#                 event_end = datetime.datetime.combine(event_end, datetime.time.min)

#             if start_of_week <= event_start <= end_of_week:
#                 summary = str(component.get('summary'))
#                 academic_events.append({
#                     'start': event_start,
#                     'end': event_end,
#                     'summary': summary
#                 })

#     return academic_events

# print(get_academic_week())
import matplotlib.pyplot as plt
from matplotlib.table import Table

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

# Example schedule text
schedule_text = """
Monday, 21:45, 22:30, Self-studying Electronics
Monday, 22:30, 23:00, Reading
Monday, 23:00, 00:30, Sleep

Tuesday, 08:00, 08:30, Workout
Tuesday, 08:30, 09:00, Free Time
Tuesday, 09:00, 17:00, Work
"""

# Display the schedule as a table
display_schedule_as_table(schedule_text)
