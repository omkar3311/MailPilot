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

