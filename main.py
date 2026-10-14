from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.routes import router
from utils.logging_config import configure_logging

configure_logging()

app = FastAPI(
    title="AI Powered Supply Chain Container Tracking System",
    version="1.0.0",
    description="Production-ready AI-powered container tracking system for supply chain shipment visibility",
)

app.include_router(router)

base_dir = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(base_dir / "ui" / "templates"))
app.mount("/ui/static", StaticFiles(directory=str(base_dir / "ui" / "static")), name="ui-static")
app.mount("/reporting/output", StaticFiles(directory=str(base_dir / "reporting" / "output")), name="reports")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/")
def root(request: Request):
    return templates.TemplateResponse(request, "customer.html")


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    return templates.TemplateResponse(request, "admin.html")


@app.get("/customer", response_class=HTMLResponse)
def customer_page(request: Request):
    return templates.TemplateResponse(request, "customer.html")


@app.get("/health", response_class=JSONResponse)
def healthcheck():
    return {"status": "ok", "service": "ai-powered-supply-chain-container-tracking-system"}
