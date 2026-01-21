from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from openpyxl import Workbook
from io import BytesIO
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime

router = APIRouter()

TO_EMAIL = "himesha.fernando@ncinga.net"

class VisitorPayload(BaseModel):
    name: str
    designation: str
    email: EmailStr

def build_excel_file(payload: VisitorPayload) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Registrations"

    # Header
    ws.append(["Name", "Designation", "Email", "Submitted At"])

    # Row
    ws.append([
        payload.name.strip(),
        payload.designation.strip(),
        payload.email,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ])

    # Save to memory
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()

def send_email_with_attachment(xlsx_bytes: bytes, payload: VisitorPayload):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    from_name = os.getenv("SMTP_FROM_NAME", "NCINGA Bot")

    if not all([smtp_host, smtp_user, smtp_pass]):
        raise RuntimeError("SMTP env vars missing: SMTP_HOST, SMTP_USER, SMTP_PASS")

    msg = EmailMessage()
    msg["Subject"] = "Temi Registration Export (Excel)"
    msg["From"] = f"{from_name} <{smtp_user}>"
    msg["To"] = TO_EMAIL

    msg.set_content(
        f"New registration received.\n\n"
        f"Name: {payload.name}\n"
        f"Designation: {payload.designation}\n"
        f"Email: {payload.email}\n"
    )

    filename = f"registration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    msg.add_attachment(
        xlsx_bytes,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename
    )

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)

@router.post("/export-and-email")
def export_and_email(payload: VisitorPayload):
    try:
        xlsx_bytes = build_excel_file(payload)
        send_email_with_attachment(xlsx_bytes, payload)
        return {"status": "sent", "to": TO_EMAIL}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except smtplib.SMTPException as e:
        raise HTTPException(status_code=502, detail=f"SMTP error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
