import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import pages

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="kijiya")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(pages.router)
