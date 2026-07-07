from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import init_db
from graphs.builder import build_graph
from memory.checkpointer import ainit_checkpointer, aclose_checkpointer
from routes import deals, approvals, webhooks, dashboard

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.
    1. Creates all SQLAlchemy tables (init_db).
    2. Initializes the AsyncSqliteSaver checkpointer (ainit_checkpointer).
       Construction is async-only (aiosqlite), so it happens here — the
       one place guaranteed to run inside the event loop before any
       request — and MUST precede build_graph(), which attaches the
       checkpointer at compile time.
    3. Pre-compiles the LangGraph StateGraph (build_graph).
       Compiling here — at startup, before the first request — means:
         a) No request ever bears the full compile cost (~200ms).
         b) No race condition where two concurrent requests both trigger
            compile() simultaneously because _compiled_graph was None.
    """
    init_db()
    await ainit_checkpointer()
    try:
        # Inside the try so a compile failure still closes the checkpointer:
        # aiosqlite's worker thread is non-daemon, and leaking it would turn
        # a fail-fast startup abort into a process hang.
        build_graph()
        yield
    finally:
        await aclose_checkpointer()


app = FastAPI(
    title="Threshold — Internal Deal-Friction Intelligence Agent",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(deals.router)
app.include_router(approvals.router)
app.include_router(webhooks.router)
app.include_router(dashboard.router)


@app.get("/")
def root():
    return {"status": "Threshold backend running"}
