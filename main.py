from fastapi import FastAPI , Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials

import sqlite3
import threading
import time 
import os

from utility import *

load_dotenv()

app = FastAPI()
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

templates = Jinja2Templates(directory = "templates")

creds = Credentials.from_authorized_user_file(
    "token.json"
)

service = gmail_service(creds)

calendar = calendar_service(creds)

client = groq_client(os.getenv("GROQ_API_KEY"))

def get_db():

    return sqlite3.connect(
        "email.db",
        check_same_thread=False
    )
conn = get_db()
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS emails(

id TEXT PRIMARY KEY,

thread_id TEXT,

sender TEXT,

subject TEXT,

body TEXT,

snippet TEXT,

email_date TEXT,

needs_reply INTEGER,

priority TEXT,

summary TEXT,

draft_reply TEXT,

input_tokens INTEGER,

output_tokens INTEGER,

total_tokens INTEGER,

status TEXT DEFAULT 'pending',

created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS drafts(

id INTEGER PRIMARY KEY AUTOINCREMENT,

email_id TEXT,

thread_id TEXT,

sender TEXT,

subject TEXT,

draft_reply TEXT,

created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

)
""")

conn.commit()

AUTO_SEND = False