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

def check_new_emails():
    cursor = conn.cursor()
    while True:
        messages = get_messages_id(service,query="in:inbox is:unread",max_results=10)
        for msg in messages:
            email = get_message(service,msg["id"])
            email = parse_email(email)
            
            if not should_analyze(email):
                continue
            
            cursor.execute(
                "SELECT * FROM emails WHERE id=?",
                (email["id"],)
            )

            db_email = cursor.fetchone()

            if db_email:

                if (AUTO_SEND and db_email[7] and db_email[14] == "pending"  ):

                    send_reply(
                        service,
                        email,
                        db_email[10]        
                    )

                    mark_as_read(
                        service,
                        email["id"]
                    )

                    cursor.execute(
                        """
                        UPDATE emails
                        SET status='sent'
                        WHERE id=?
                        """,
                        (email["id"],)
                    )

                    conn.commit()

                continue            

            result = ask_groq(
                client,
                email
            )
            if result["meeting_request"]:

                result = handle_meeting_request(
                    calendar,
                    client,
                    email,
                    result
                )
            usage = result.get("usage", {})

            cursor.execute("""

            INSERT INTO emails(id,thread_id,sender,subject,body,snippet,email_date,needs_reply,priority,summary,draft_reply,input_tokens,output_tokens,total_tokens)

            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)

            """,(email["id"],email["thread_id"],email["from"],email["subject"],email["body"],email["snippet"],email["date"],result["needs_reply"],result["priority"],result["summary"],result["draft_reply"],usage.get("prompt_tokens",0),usage.get("completion_tokens",0),usage.get("total_tokens",0)))
            
            conn.commit()
            
            if AUTO_SEND and result["needs_reply"]:
                send_reply(
                    service,
                    email,
                    result["draft_reply"]
                )
                mark_as_read(
                    service,
                    email["id"]
                )
                cursor.execute("""
                    UPDATE emails
                    SET status='sent'
                    WHERE id=?
                    """,(email["id"],))

                conn.commit()
        time.sleep(15)
