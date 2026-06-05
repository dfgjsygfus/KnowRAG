from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.app.api.chat import router as chat_router
from backend.app.api.documents import router as documents_router
from backend.app.api.ingestion import router as ingestion_router
from backend.app.api.retrieval import router as retrieval_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:1420",
        "http://localhost:1420",
        "http://tauri.localhost",
        "tauri://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(documents_router)
app.include_router(ingestion_router)
app.include_router(retrieval_router)
app.include_router(chat_router)
ADMIN_CONSOLE_PATH = Path(__file__).resolve().parent / "frontend" / "index.html"
ADMIN_CONSOLE_SCRIPT_PATH = Path(__file__).resolve().parent / "frontend" / "app.js"


@app.get("/admin", include_in_schema=False)
async def admin_console():
    return FileResponse(ADMIN_CONSOLE_PATH, headers={"Cache-Control": "no-store"})


@app.get("/admin/app.js", include_in_schema=False)
async def admin_console_script():
    return FileResponse(
        ADMIN_CONSOLE_SCRIPT_PATH,
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
