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