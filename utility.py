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
