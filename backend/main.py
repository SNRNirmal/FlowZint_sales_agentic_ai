from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import init_db
from routes import deals, approvals, webhooks, dashboard

app = FastAPI(title="Threshold — Internal Deal-Friction Intelligence Agent")

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


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def root():
    return {"status": "Threshold backend running"}
