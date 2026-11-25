import os
import json
import uuid
import tempfile
from datetime import datetime, timedelta
from flask import Blueprint, request, redirect, url_for, session, flash, render_template
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

export_bp = Blueprint("export", __name__)

# 改用完整 calendar 權限，先可以幫用家建立獨立嘅副日曆
SCOPES = ["https://www.googleapis.com/auth/calendar"]
CLIENT_SECRETS_FILE = "credentials.json"

DAY_OFFSET = {
    "Mon": 0,
    "Tue": 1,
    "Wed": 2,
    "Thu": 3,
    "Fri": 4,
    "Sat": 5,
    "Sun": 6,
}


@export_bp.route("/export/report", methods=["POST"])
def open_report():
    table_html = request.form.get("table_html", "")
    courses_html = request.form.get("courses_html", "")
    total_weeks = int(request.form.get("total_weeks") or 13)

    return render_template(
        "report.html",
        table_html=table_html,
        courses_html=courses_html,
        total_weeks=total_weeks,
    )


@export_bp.route("/export/gcal/start", methods=["POST"])
def start_gcal_sync():
    events_json = request.form.get("events_json", "[]")
    sem_start_date = request.form.get("sem_start_date", "")

    if not sem_start_date:
        flash("Please select Week 1 Monday date.")
        return redirect(url_for("main.index"))

    if not os.path.exists(CLIENT_SECRETS_FILE):
        flash("Missing credentials.json in project root folder.")
        return redirect(url_for("main.index"))

    temp_id = str(uuid.uuid4())
    temp_path = os.path.join(tempfile.gettempdir(), f"gcal_{temp_id}.json")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(
            {"events_json": events_json, "sem_start_date": sem_start_date},
            f,
            ensure_ascii=False,
        )

    session["gcal_temp_file"] = temp_path
    session["gcal_action"] = "sync"

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=url_for("export.gcal_callback", _external=True),
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
    )
    session["oauth_state"] = state
    session["oauth_code_verifier"] = flow.code_verifier
    return redirect(authorization_url)


@export_bp.route("/export/gcal/clear", methods=["POST"])
def start_gcal_clear():
    if not os.path.exists(CLIENT_SECRETS_FILE):
        flash("Missing credentials.json in project root folder.")
        return redirect(url_for("main.index"))

    session["gcal_action"] = "clear"

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=url_for("export.gcal_callback", _external=True),
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
    )
    session["oauth_state"] = state
    session["oauth_code_verifier"] = flow.code_verifier
    return redirect(authorization_url)


@export_bp.route("/export/gcal/callback")
def gcal_callback():
    state = session.get("oauth_state")
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for("export.gcal_callback", _external=True),
    )
    flow.code_verifier = session.pop("oauth_code_verifier", None)
    flow.fetch_token(authorization_response=request.url)

    creds = flow.credentials
    service = build("calendar", "v3", credentials=creds)
    action = session.pop("gcal_action", "sync")

    # 動作 A：一鍵刪除所有由本系統建立嘅「Class Timetable」副日曆（方便測試）
    if action == "clear":
        deleted_cals = 0
        cal_list = service.calendarList().list().execute().get("items", [])
        for cal in cal_list:
            if cal.get("summary") == "Class Timetable" and not cal.get("primary"):
                service.calendars().delete(calendarId=cal["id"]).execute()
                deleted_cals += 1

        flash(f"Removed {deleted_cals} 'Class Timetable' calendar(s) from your Google Calendar!")
        return redirect(url_for("main.index"))

    # 動作 B：建立獨立「Class Timetable」副日曆並寫入所有堂課
    temp_path = session.pop("gcal_temp_file", None)
    if not temp_path or not os.path.exists(temp_path):
        flash("Session expired or timetable data not found. Please try again.")
        return redirect(url_for("main.index"))

    try:
        with open(temp_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        parsed_classes = json.loads(payload.get("events_json", "[]"))
        week1_monday = datetime.strptime(payload.get("sem_start_date"), "%Y-%m-%d").date()
    except Exception as e:
        flash(f"Failed to parse schedule data: {e}")
        return redirect(url_for("main.index"))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    # 先開一個專屬副日曆
    new_calendar = {
        "summary": "Class Timetable",
        "description": "Auto-generated class schedule",
        "timeZone": "Asia/Hong_Kong",
    }
    created_cal = service.calendars().insert(body=new_calendar).execute()
    target_calendar_id = created_cal["id"]

    created_count = 0

    for item in parsed_classes:
        day_name = item.get("day")
        if day_name not in DAY_OFFSET:
            continue

        day_offset = DAY_OFFSET[day_name]
        start_time_str = item.get("start_time", "09:00")
        end_time_str = item.get("end_time", "09:50")
        weeks = item.get("weeks") or []

        for w in weeks:
            try:
                w_num = int(w)
            except ValueError:
                continue

            class_date = week1_monday + timedelta(weeks=(w_num - 1), days=day_offset)
            start_dt = f"{class_date.isoformat()}T{start_time_str}:00+08:00"
            end_dt = f"{class_date.isoformat()}T{end_time_str}:00+08:00"

            event_body = {
                "summary": item.get("title", "Class"),
                "location": item.get("room", ""),
                "description": f"Week {w_num}\n{item.get('note', '')}".strip(),
                "start": {
                    "dateTime": start_dt,
                    "timeZone": "Asia/Hong_Kong",
                },
                "end": {
                    "dateTime": end_dt,
                    "timeZone": "Asia/Hong_Kong",
                },
            }

            service.events().insert(calendarId=target_calendar_id, body=event_body).execute()
            created_count += 1

    flash(f"Created 'Class Timetable' calendar and added {created_count} class sessions!")
    return redirect(url_for("main.index"))