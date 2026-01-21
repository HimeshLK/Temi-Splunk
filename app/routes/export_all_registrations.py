from fastapi import APIRouter, HTTPException
from openpyxl import Workbook
from io import BytesIO
from datetime import datetime
import os
import smtplib
from email.message import EmailMessage

# ✅ USE THE SAME COLLECTION YOUR APP USES
from app.db import registrations

router = APIRouter()
TO_EMAIL = "himesha.fernando@ncinga.net"


def build_excel(rows: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Registrations"

    ws.append(["Event ID", "Name", "Designation", "Email", "Created At", "Source"])

    for r in rows:
        ws.append([
            r.get("event_id", ""),
            r.get("name", ""),
            r.get("designation", ""),
            r.get("email", ""),
            r.get("created_at", ""),
            r.get("source", ""),
        ])

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def send_email(xlsx_bytes: bytes, total: int):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    from_name = os.getenv("SMTP_FROM_NAME", "NCINGA Bot")

    if not all([smtp_host, smtp_user, smtp_pass]):
        raise RuntimeError("Missing SMTP_HOST/SMTP_USER/SMTP_PASS in env")

    msg = EmailMessage()
    msg["Subject"] = f"Temi Registrations Export ({total} records)"
    msg["From"] = f"{from_name} <{smtp_user}>"
    msg["To"] = TO_EMAIL

    msg.set_content(f"Attached: registrations export. Total records: {total}")

    filename = f"temi_registrations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    msg.add_attachment(
        xlsx_bytes,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)


@router.post("/export-registrations-email")
async def export_registrations_email():
    cursor = registrations.find({}, {"_id": 0}).sort("created_at", -1)  # ✅ SAME COLLECTION
    rows = await cursor.to_list(length=100000)

    if not rows:
        raise HTTPException(status_code=404, detail="No registrations found in database")

    xlsx_bytes = build_excel(rows)
    send_email(xlsx_bytes, total=len(rows))

    return {"status": "sent", "to": TO_EMAIL, "count": len(rows)}
