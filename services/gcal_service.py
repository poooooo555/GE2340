import os
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

DAY_OFFSET = {
    "Mon": 0,
    "Tue": 1,
    "Wed": 2,
    "Thu": 3,
    "Fri": 4,
    "Sat": 5,
    "Sun": 6,
}


def get_google_auth_flow(redirect_uri: str) -> Flow:
    client_config = {
        "web": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )


def _parse_time_range(time_str: str):
    """將 '12:00 - 12:50' 拆成 ('12:00', '12:50')"""
    parts = [p.strip() for p in time_str.split("-")]
    if len(parts) != 2:
        return None, None
    return parts[0], parts[1]


def sync_schedule_to_gcal(creds_dict: dict, schedule: dict, sem_start_monday: str) -> int:
    """
    sem_start_monday: 格式 'YYYY-MM-DD' (Semester Week 1 嘅星期一)
    回傳成功新增嘅 Event 數量
    """
    creds = Credentials(**creds_dict)
    service = build("calendar", "v3", credentials=creds)

    base_monday = datetime.strptime(sem_start_monday, "%Y-%m-%d").date()
    rows = schedule.get("rows") or []
    created_count = 0

    for row in rows:
        start_t, end_t = _parse_time_range(row.get("time", ""))
        if not start_t or not end_t:
            continue

        cells = row.get("cells") or {}
        for day_name, entries in cells.items():
            if day_name not in DAY_OFFSET:
                continue
            day_offset = DAY_OFFSET[day_name]

            for entry in entries:
                weeks = entry.get("weeks") or []
                course = entry.get("course", "Class")
                section = entry.get("section", "")
                room = entry.get("room", "")
                note = entry.get("note", "")

                summary = f"{course} ({section})" if section else course
                desc_parts = [f"Week schedule: {entry.get('weeks_display', '')}"]
                if note:
                    desc_parts.append(f"Note: {note}")
                description = "\n".join(desc_parts)

                # 根據實際上堂嘅 Week 逐堂加入日曆（避開無堂嘅週數）
                for w in weeks:
                    try:
                        w_num = int(w)
                    except (ValueError, TypeError):
                        continue

                    class_date = base_monday + timedelta(weeks=w_num - 1, days=day_offset)
                    start_iso = f"{class_date.isoformat()}T{start_t}:00+08:00"
                    end_iso = f"{class_date.isoformat()}T{end_t}:00+08:00"

                    event_body = {
                        "summary": summary,
                        "location": room,
                        "description": description,
                        "start": {"dateTime": start_iso, "timeZone": "Asia/Hong_Kong"},
                        "end": {"dateTime": end_iso, "timeZone": "Asia/Hong_Kong"},
                    }
                    service.events().insert(calendarId="primary", body=event_body).execute()
                    created_count += 1

    return created_count