from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
def serve_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@router.get("/health")
def health():
    return {"status": "ok", "service": "greencompute-api"}