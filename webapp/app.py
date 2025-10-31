from __future__ import annotations

import os
import subprocess
import json
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

# Use absolute imports (sibling package)
from email_agent.reporter import send_immediate_test_report  # type: ignore
from email_agent.runner import run_once  # type: ignore
from email_agent.auth_manager import AuthManager, EmailCredentials  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PID_FILE = PROJECT_ROOT / ".email_agent.pid"
LOG_DIR = PROJECT_ROOT
START_SCRIPT = PROJECT_ROOT / "start_email_agent.sh"
ACCOUNTS_REGISTRY = PROJECT_ROOT / ".email_accounts.json"

DASH_USER = os.getenv("DASH_USER", "admin")
DASH_PASS = os.getenv("DASH_PASS", "admin")

security = HTTPBasic()

env = Environment(
    loader=FileSystemLoader(str((PROJECT_ROOT / "webapp" / "templates").resolve())),
    autoescape=select_autoescape(["html", "xml"]),
)

app = FastAPI(title="Email Agent Control Panel")

app.mount("/static", StaticFiles(directory=str((PROJECT_ROOT / "webapp" / "static").resolve())), name="static")


def auth_guard(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, DASH_USER)
    correct_password = secrets.compare_digest(credentials.password, DASH_PASS)
    if not (correct_username and correct_password):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


def get_status() -> dict:
    pid = None
    running = False
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            running = True
        except Exception:
            running = False
    latest_log = get_latest_log_file()
    return {"running": running, "pid": pid, "latest_log": latest_log.name if latest_log else None}


def get_latest_log_file() -> Optional[Path]:
    logs = sorted(LOG_DIR.glob("email_agent_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0] if logs else None


def load_known_accounts() -> List[str]:
    # Try registry file
    if ACCOUNTS_REGISTRY.exists():
        try:
            return json.loads(ACCOUNTS_REGISTRY.read_text())
        except Exception:
            pass
    # Try env var fallback
    env_accounts = os.getenv("EMAIL_AGENT_ACCOUNTS", "").strip()
    if env_accounts:
        return [a.strip() for a in env_accounts.split(",") if a.strip()]
    return []


def save_account(email: str):
    """Add email to registry if not already present"""
    accounts = load_known_accounts()
    if email not in accounts:
        accounts.append(email)
        ACCOUNTS_REGISTRY.write_text(json.dumps(accounts, indent=2))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, authorized: bool = Depends(auth_guard)):
    template = env.get_template("index.html")
    status = get_status()
    accounts = load_known_accounts()
    return template.render(status=status, accounts=accounts)


@app.get("/register", response_class=HTMLResponse)
async def register_form(request: Request, authorized: bool = Depends(auth_guard)):
    template = env.get_template("register.html")
    return template.render()


@app.post("/register")
async def register_account(
    authorized: bool = Depends(auth_guard),
    email: str = Form(...),
    imap_host: str = Form("imap.gmail.com"),
    imap_password: str = Form(...),
    smtp_host: str = Form("smtp.gmail.com"),
    smtp_password: str = Form(...),
):
    try:
        auth_mgr = AuthManager(email)
        creds = EmailCredentials(
            username=email,
            imap_host=imap_host,
            imap_password=imap_password,
            smtp_host=smtp_host,
            smtp_password=smtp_password,
        )
        if auth_mgr.store_credentials(creds, force_update=True):
            save_account(email)
            return RedirectResponse(url="/?registered=success", status_code=303)
        else:
            raise HTTPException(status_code=400, detail="Failed to store credentials")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/start")
async def start_agent(
    authorized: bool = Depends(auth_guard),
    email: str = Form(...),
    report_email: str = Form("ami.krs@gmail.com"),
    enable_reporting: Optional[str] = Form(None),
):
    if not START_SCRIPT.exists():
        raise HTTPException(status_code=500, detail="start_email_agent.sh not found")
    if get_status()["running"]:
        return RedirectResponse(url="/", status_code=303)

    args = ["bash", str(START_SCRIPT), email, report_email]
    if enable_reporting:
        args.append("reporting")
    subprocess.Popen(args, cwd=str(PROJECT_ROOT))
    return RedirectResponse(url="/", status_code=303)


@app.post("/stop")
async def stop_agent(authorized: bool = Depends(auth_guard)):
    if not PID_FILE.exists():
        return RedirectResponse(url="/", status_code=303)
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 15)
    except Exception:
        pass
    finally:
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
    return RedirectResponse(url="/", status_code=303)


@app.post("/test-reply")
async def test_reply(
    authorized: bool = Depends(auth_guard),
    email: str = Form(...),
):
    try:
        # Use runner to process one unseen email with stored creds
        code = run_once(sender_email=email, receiver_email=None, use_stored=True)
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/test-report")
async def test_report(
    authorized: bool = Depends(auth_guard),
    email: str = Form(...),
    report_email: str = Form("ami.krs@gmail.com"),
):
    try:
        send_immediate_test_report(report_email=report_email, sender_email=email)
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs", response_class=PlainTextResponse)
async def logs(lines: int = 200, authorized: bool = Depends(auth_guard)):
    log_file = get_latest_log_file()
    if not log_file:
        return "No logs yet."
    try:
        with log_file.open("r") as f:
            content = f.readlines()
        return "".join(content[-max(1, min(lines, 2000)):])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/healthz")
async def healthz():
    return {"ok": True}
