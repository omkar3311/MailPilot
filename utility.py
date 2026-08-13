import os
import json
import base64
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from groq import Groq
from dotenv import load_dotenv
import os
from email.mime.text import MIMEText
from datetime import datetime, timedelta

import re

load_dotenv()

def clean_text(text):

    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)

    text = re.sub(r'https?://\S+', '', text)

    text = re.sub(r'\n{3,}', '', text)

    return text.strip()

def gmail_service(creds):

    return build(
        "gmail",
        "v1",
        credentials=creds
    )
    
def calendar_service(creds):
    return build(
    "calendar",
    "v3",
    credentials=creds
)

def check_calendar_availability(
    service,
    start_time,
    end_time
):
    body = {
        "timeMin": start_time.isoformat(),
        "timeMax": end_time.isoformat(),
        "items": [
            {
                "id": "primary"
            }
        ]
    }

    result = service.freebusy().query(
        body=body
    ).execute()

    busy = result["calendars"]["primary"]["busy"]

    return len(busy) == 0

def create_calendar_event(
    service,
    title,
    start_time,
    end_time,
    attendee_email=None,
    description=""
):

    event = {
        "summary": title,

        "description": description,

        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "Asia/Kolkata"
        },

        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "Asia/Kolkata"
        }
    }

    if attendee_email:
        event["attendees"] = [
            {
                "email": attendee_email
            }
        ]

    return service.events().insert(
        calendarId="primary",
        body=event,
        sendUpdates="all"
    ).execute()
    
def update_calendar_event(
    service,
    event_id,
    title,
    start_time,
    end_time
):

    event = service.events().get(
        calendarId="primary",
        eventId=event_id
    ).execute()

    event["summary"] = title

    event["start"] = {
        "dateTime": start_time.isoformat(),
        "timeZone": "Asia/Kolkata"
    }

    event["end"] = {
        "dateTime": end_time.isoformat(),
        "timeZone": "Asia/Kolkata"
    }

    return service.events().update(
        calendarId="primary",
        eventId=event_id,
        body=event,
        sendUpdates="all"
    ).execute()
    
def delete_calendar_event(
    service,
    event_id
):

    service.events().delete(
        calendarId="primary",
        eventId=event_id,
        sendUpdates="all"
    ).execute()
    
import re

def extract_email(sender):

    match = re.search(r'<(.+?)>', sender)

    if match:
        return match.group(1)

    return sender    

def handle_meeting_request(calendar, client, email, result):

    if not result.get("meeting_request"):
        return result

    start = datetime.fromisoformat(
        result["meeting_datetime"]
    )

    duration = result.get("duration", 60)

    end = start + timedelta(minutes=duration)

    available = check_calendar_availability(
        calendar,
        start,
        end
    )

    if available:

        attendee = extract_email(email["from"])

        event = create_calendar_event(
            service=calendar,
            title=email["subject"],
            start_time=start,
            end_time=end,
            attendee_email=attendee,
            description=email["body"]
        )

        result["calendar_status"] = "booked"
        result["calendar_event_id"] = event["id"]

        return result

    slots = find_available_slots(
        calendar,
        start.date(),
        duration
    )

    result["calendar_status"] = "busy"

    result["available_slots"] = [
        s[0].strftime("%d %b %Y %I:%M %p")
        for s in slots[:5]
    ]

    updated = ask_groq(
        client,
        email,
        result=result,
        slots=result["available_slots"]
    )

    result["draft_reply"] = updated["draft_reply"]

    return result

def today_events(service):

    now = datetime.now()

    end = now + timedelta(days=1)

    events = service.events().list(

        calendarId="primary",

        timeMin=now.isoformat(),

        timeMax=end.isoformat(),

        singleEvents=True,

        orderBy="startTime"

    ).execute()

    return events.get(
        "items",
        []
    )