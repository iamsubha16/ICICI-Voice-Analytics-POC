import os
import shutil
import uuid
from datetime import datetime
from fastapi import FastAPI, Request, Form, File, UploadFile, BackgroundTasks, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.config import Config
from app.auth import verify_password, sign_session, verify_session, get_current_user_redirect
from app.pipeline.analyzer import run_pipeline_task, JOBS_STORE

app = FastAPI(title="DataSutram Echo — Voice Analytics Platform", version="2.0.0")

# Setup folder paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Create static directories if they do not exist
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "samples"), exist_ok=True)

# Mount static files and templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# ============================================================
# Helper: no-cache headers for authenticated pages
# ============================================================
def _no_cache_headers(response):
    """Prevent browser back-button from restoring protected pages after logout."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# ============================================================
# Page Routes
# ============================================================


@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    user = get_current_user_redirect(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response = templates.TemplateResponse(request=request, name="index.html", context={"user": user})
    return _no_cache_headers(response)


@app.get("/login", response_class=HTMLResponse)
async def get_login_page(request: Request):
    user = get_current_user_redirect(request)
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})


@app.post("/login")
async def handle_login(request: Request, email: str = Form(...), password: str = Form(...)):
    # Verify email
    if email.strip().lower() != Config.LOGIN_EMAIL.strip().lower():
        return templates.TemplateResponse(
            request=request, name="login.html", context={"error": "Invalid email address or credentials."}
        )

    # Verify password hash
    if not verify_password(password, Config.LOGIN_PASSWORD_HASH):
        return templates.TemplateResponse(
            request=request, name="login.html", context={"error": "Invalid password. Access denied."}
        )

    # Valid credentials — set session cookie, redirect to dashboard
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    session_id = sign_session(email)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=3600 * 12,  # 12 hours
        samesite="lax",
    )
    return response


@app.get("/logout")
async def handle_logout():
    """
    Delete session cookie and redirect to login.
    The login page itself has no cache-control restrictions, so pressing
    Back will just return to login, not the dashboard (which has no-store headers).
    """
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="session_id")
    # Also add no-cache to the redirect itself
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


# ============================================================
# Auth Check (lightweight — called by frontend on page load)
# ============================================================


@app.get("/api/auth-check")
async def auth_check(request: Request):
    """
    Called by the frontend JS on every page load.
    Returns 401 if session is missing or expired, 200 if valid.
    This ensures that even if the browser restores a cached dashboard
    page via Back button, the JS will catch the 401 and redirect to /login.
    """
    session_cookie = request.cookies.get("session_id")
    if not session_cookie or not verify_session(session_cookie):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid")
    return JSONResponse({"ok": True})


# ============================================================
# Call History API
# ============================================================


@app.get("/api/calls/history")
async def get_call_history(request: Request):
    """
    Returns a summary list of all completed call jobs from JOBS_STORE.
    Used to populate the Previous Calls panel on the dashboard.
    """
    session_cookie = request.cookies.get("session_id")
    if not session_cookie or not verify_session(session_cookie):
        raise HTTPException(status_code=401, detail="Unauthorized session")

    history = []
    for call_id, job in JOBS_STORE.items():
        # Only include completed jobs
        if job.get("status") != 100:
            continue

        report = job.get("report") or {}
        history.append(
            {
                "call_id": call_id,
                "agent_id": report.get("agent_id", "—"),
                "customer_id": report.get("customer_id", "—"),
                "lender_name": report.get("lender_name", "—"),
                "loan_account": report.get("loan_account", "—"),
                "overdue_amount": report.get("overdue_amount", 0),
                "processed_at": report.get("processed_at", ""),
                "disposition": (
                    report.get("disposition_verification", {}).get("d1_inferred_disposition")
                    or report.get("disposition_verification", {}).get("ai_disposition")
                    or "—"
                ),
            }
        )

    # Most recent first
    history.sort(key=lambda x: x.get("processed_at") or "", reverse=True)
    return JSONResponse(history)


# ============================================================
# Core Analysis API
# ============================================================


@app.post("/api/analyze")
async def analyze_call(
    background_tasks: BackgroundTasks,
    request: Request,
    call_id: str = Form(None),
    agent_id: str = Form(...),
    customer_id: str = Form(...),
    disposition_code: str = Form(...),
    disposition_notes: str = Form(""),
    call_datetime: str = Form(...),
    lender_name: str = Form(...),
    loan_account: str = Form(...),
    overdue_amount: float = Form(...),
    audio_file: UploadFile = File(None),
    sample_file: str = Form(None),
):
    # Verify authentication
    session_cookie = request.cookies.get("session_id")
    if not session_cookie or not verify_session(session_cookie):
        raise HTTPException(status_code=401, detail="Unauthorized session")

    # Enforce unique call_id
    if not call_id:
        call_id = f"CALL_{uuid.uuid4().hex[:8].upper()}"

    # Handle audio source
    audio_path = ""
    filename = ""

    if sample_file:
        filename = sample_file
        audio_path = os.path.join(STATIC_DIR, "samples", sample_file)
        if not os.path.exists(audio_path):
            with open(audio_path, "wb") as f:
                f.write(b"MOCK_AUDIO_BUFFER")
    else:
        if not audio_file or not audio_file.filename:
            raise HTTPException(status_code=400, detail="Missing call recording file upload")

        filename = audio_file.filename
        audio_path = os.path.join(Config.UPLOAD_DIR, f"{call_id}_{filename}")

        with open(audio_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)

    # Trigger compliance pipeline asynchronously
    background_tasks.add_task(
        run_pipeline_task,
        call_id,
        agent_id,
        customer_id,
        disposition_code,
        disposition_notes,
        call_datetime,
        lender_name,
        loan_account,
        overdue_amount,
        audio_path,
        filename,
    )

    return JSONResponse({"call_id": call_id})


@app.get("/api/status/{call_id}")
async def get_job_status(call_id: str, request: Request):
    # Verify authentication
    session_cookie = request.cookies.get("session_id")
    if not session_cookie or not verify_session(session_cookie):
        raise HTTPException(status_code=401, detail="Unauthorized session")

    if call_id not in JOBS_STORE:
        raise HTTPException(status_code=404, detail="Job session not found")

    return JSONResponse(JOBS_STORE[call_id])
