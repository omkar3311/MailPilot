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

def clean_text(text):
    
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)

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
    
def groq_client(api_key):
    return Groq(
    api_key=os.getenv("GROQ_API_KEY")
)
    
def get_messages_id(
    service,
    query="in:inbox",
    max_results=10
):
    results = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=max_results
    ).execute()

    return results.get("messages", [])

def get_message(service, message_id):

    return service.users().messages().get(
        userId="me",
        id=message_id,
        format="full"
    ).execute()

def extract_email_text(payload):
    text = None
    html = None

    def walk(part):
        nonlocal text, html

        mime = part.get("mimeType", "")

        if mime == "text/plain":
            data = part["body"].get("data")
            if data:
                text = base64.urlsafe_b64decode(data).decode(
                    "utf-8",
                    errors="ignore"
                )

        elif mime == "text/html":
            data = part["body"].get("data")
            if data:
                html = base64.urlsafe_b64decode(data).decode(
                    "utf-8",
                    errors="ignore"
                )

        for child in part.get("parts", []):
            walk(child)

    walk(payload)

    if text and len(text.strip()) > 50:
        return text

    if html:
        return BeautifulSoup(html, "html.parser").get_text("\n", strip=True)

    return ""

def clean_text(text):

    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)

    text = re.sub(r'https?://\S+', '', text)

    text = re.sub(r'\n{3,}', '', text)

    return text.strip()

def parse_email(message):
    

    headers = message["payload"]["headers"]

    sender = ""
    subject = ""
    date = ""

    for h in headers:

        if h["name"] == "From":
            sender = h["value"]

        elif h["name"] == "Subject":
            subject = h["value"]

        elif h["name"] == "Date":
            date = h["value"]

    body = extract_email_text(message["payload"])
    body = clean_text(body)
    return {

        "id": message["id"],

        "thread_id": message["threadId"],
        
        "payload": message["payload"],

        "from": sender,

        "subject": subject,

        "date": date,

        "snippet": message.get(
            "snippet",
            ""
        ),

        # "body": extract_email_text(
        #     message["payload"]
        # )
        "body" :body

    }
def should_analyze(email):

    sender = email["from"].lower()
    subject = email["subject"].lower()

    if "noreply" in sender:
        return False

    if "no-reply" in sender:
        return False

    if "newsletter" in sender:
        return False

    if "marketing@" in sender:
        return False

    if "receipt" in sender:
        return False

    if "promotion" in subject:
        return False

    return True


def send_reply(service, email, reply):

    to_email = email["from"]

    if "<" in to_email:
        to_email = (
            to_email
            .split("<")[1]
            .replace(">", "")
            .strip()
        )

    message = MIMEText(reply)

    message["To"] = to_email

    if email["subject"].startswith("Re:"):
        message["Subject"] = email["subject"]
    else:
        message["Subject"] = f"Re: {email['subject']}"

    if email.get("message_id"):
        message["In-Reply-To"] = email["message_id"]

    if email.get("references"):
        message["References"] = (
            email["references"] + " " + email["message_id"]
        )
    elif email.get("message_id"):
        message["References"] = email["message_id"]

    raw = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()

    body = {
        "raw": raw,
        "threadId": email["thread_id"]
    }

    return service.users().messages().send(
        userId="me",
        body=body
    ).execute()
    
def mark_as_read(service, message_id):

    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={
            "removeLabelIds": ["UNREAD"]
        }
    ).execute()
    
def create_draft(service, email, reply):

    to_email = email["from"]

    if "<" in to_email:
        to_email = to_email.split("<")[1].replace(">", "").strip()

    message = MIMEText(reply)

    message["To"] = to_email

    if email["subject"].startswith("Re:"):
        message["Subject"] = email["subject"]
    else:
        message["Subject"] = f"Re: {email['subject']}"

    headers = email["payload"]["headers"]

    message_id = ""
    references = ""

    for h in headers:

        if h["name"] == "Message-ID":
            message_id = h["value"]

        elif h["name"] == "References":
            references = h["value"]

    if message_id:
        message["In-Reply-To"] = message_id

    if references:
        message["References"] = references + " " + message_id
    elif message_id:
        message["References"] = message_id

    raw = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()

    draft = {
        "message": {
            "raw": raw,
            "threadId": email["thread_id"]
        }
    }

    return service.users().drafts().create(
        userId="me",
        body=draft
    ).execute()
    
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

    
def ask_groq(client, email, result=None, slots=None):
    background = """
    I'm Omkar Waghmare ,AI Intern at AIAdventures.
    """
    
    prompt = f"""
Analyze this email and return JSON only.

Email:
From: {email["from"]}
Subject: {email["subject"]}
Body:
{email["body"][:3000]}

Return:
{{
"needs_reply":true,
"priority":"high|medium|low",
"summary":"...",
"meeting_request":false,
"meeting_datetime":null,
"duration":60,
"draft_reply":"..."
}}

Use ISO format (YYYY-MM-DDTHH:MM:SS). If no meeting is requested, set meeting_request=false and meeting_datetime=null.
"""

    if result and slots:

        prompt = f"""
Rewrite this email reply.

Original reply:
{result["draft_reply"]}

Requested meeting:
{result["meeting_datetime"]}

Unavailable.

Available slots:
{", ".join(slots)}

Return JSON only:

{{"draft_reply":"..."}}
"""

    response = client.chat.completions.create(

        model="llama-3.3-70b-versatile",

        temperature=0.2,

        response_format={
            "type": "json_object"
        },

        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]

    )
    print(response.usage)
    # return json.loads(
    #     response.choices[0].message.content
    # )
    result = json.loads(
        response.choices[0].message.content
    )

    result["usage"] = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens
    }

    return result

def extract_email(sender):
    match = re.search(r'<(.+?)>', sender)
    if match:
        return match.group(1)
    return sender

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

def find_available_slots(
    service,
    date,
    duration_minutes=60
):
    
    slots = []

    start_hour = 9
    end_hour = 18
    for hour in range(start_hour, end_hour):
        start = datetime(
            date.year,
            date.month,
            date.day,
            hour,
            0
        )
        end = start + timedelta(
            minutes=duration_minutes
        )
        if check_calendar_availability(
            service,
            start,
            end
        ):
            slots.append(
                (
                    start,
                    end
                )
            )
    return slots    



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
