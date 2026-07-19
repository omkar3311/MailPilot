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