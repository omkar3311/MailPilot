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