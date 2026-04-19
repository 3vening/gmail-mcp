"""Gmail API client. Handles messages, threads, drafts, attachments, labels."""
import base64
import mimetypes
import os
import time
from email.mime.application import MIMEApplication
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import html2text
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

MIN_PLAIN_TEXT_LENGTH = 40  # below this, prefer HTML-converted text
MAX_BODY_CHARS = 20_000  # truncate bodies past this unless full=True
RETRY_STATUSES = {429, 500, 502, 503, 504}


def get_service(creds: Credentials):
    """Build Gmail API service for the given credentials."""
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _retry(fn, attempts: int = 3, base_delay: float = 0.5):
    """Simple retry wrapper for transient Gmail API errors."""
    for attempt in range(attempts):
        try:
            return fn()
        except HttpError as e:
            status = getattr(e.resp, "status", None)
            if status in RETRY_STATUSES and attempt < attempts - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
            raise


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def _walk_parts(payload: dict):
    """Yield every leaf MIME part in depth-first order."""
    parts = payload.get("parts")
    if not parts:
        yield payload
        return
    for p in parts:
        yield from _walk_parts(p)


def _extract_body(payload: dict, prefer_html_when_plain_short: bool = True) -> str:
    """Pull the best text body from a MIME payload. Falls back HTML→plain when useful."""
    plain_parts = []
    html_parts = []
    for part in _walk_parts(payload):
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if not data:
            continue
        if mime == "text/plain":
            plain_parts.append(_decode(data))
        elif mime == "text/html":
            html_parts.append(_decode(data))

    plain = "\n\n".join(p.strip() for p in plain_parts if p.strip())
    html = "\n\n".join(h for h in html_parts if h.strip())

    if plain and (not prefer_html_when_plain_short or len(plain) >= MIN_PLAIN_TEXT_LENGTH):
        return plain
    if html:
        h = html2text.HTML2Text()
        h.body_width = 0
        h.ignore_images = True
        h.ignore_emphasis = False
        return h.handle(html).strip()
    return plain or ""


def _extract_attachments_meta(payload: dict) -> list[dict]:
    """Return [{filename, mime_type, size, attachment_id}] for all attached parts."""
    out = []
    for part in _walk_parts(payload):
        filename = part.get("filename")
        body = part.get("body", {})
        attach_id = body.get("attachmentId")
        if filename and attach_id:
            out.append({
                "filename": filename,
                "mime_type": part.get("mimeType", "application/octet-stream"),
                "size": body.get("size", 0),
                "attachment_id": attach_id,
            })
    return out


def search_messages(creds: Credentials, query: str, max_results: int = 10) -> list[dict]:
    """List messages matching a Gmail search query. Returns summaries (headers + snippet)."""
    service = get_service(creds)
    results = _retry(lambda: service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute())

    messages = results.get("messages", [])
    summaries = []
    for msg in messages:
        detail = _retry(lambda mid=msg["id"]: service.users().messages().get(
            userId="me", id=mid,
            format="metadata",
            metadataHeaders=["From", "To", "Subject", "Date"],
        ).execute())
        headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
        summaries.append({
            "id": msg["id"],
            "thread_id": msg.get("threadId"),
            "subject": headers.get("Subject", "(no subject)"),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "date": headers.get("Date", ""),
            "snippet": detail.get("snippet", "")[:150],
        })
    return summaries


def get_message(creds: Credentials, message_id: str, full: bool = False) -> dict:
    """Fetch full message. body is truncated to MAX_BODY_CHARS unless full=True."""
    service = get_service(creds)
    msg = _retry(lambda: service.users().messages().get(
        userId="me", id=message_id, format="full"
    ).execute())

    payload = msg.get("payload", {})
    headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
    body = _extract_body(payload)
    truncated = False
    if not full and len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS] + f"\n\n[... body truncated at {MAX_BODY_CHARS} chars. Call again with full=True for the rest.]"
        truncated = True

    return {
        "id": msg["id"],
        "thread_id": msg.get("threadId"),
        "subject": headers.get("Subject", "(no subject)"),
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "cc": headers.get("Cc", ""),
        "date": headers.get("Date", ""),
        "body": body,
        "truncated": truncated,
        "labels": msg.get("labelIds", []),
        "attachments": _extract_attachments_meta(payload),
        "message_id_header": headers.get("Message-ID", ""),
    }


def get_thread(creds: Credentials, thread_id: str, full: bool = False) -> dict:
    """Fetch every message in a thread. Returns messages in chronological order."""
    service = get_service(creds)
    thread = _retry(lambda: service.users().threads().get(
        userId="me", id=thread_id, format="full"
    ).execute())

    messages = []
    for msg in thread.get("messages", []):
        payload = msg.get("payload", {})
        headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
        body = _extract_body(payload)
        if not full and len(body) > MAX_BODY_CHARS:
            body = body[:MAX_BODY_CHARS] + f"\n\n[... truncated at {MAX_BODY_CHARS} chars.]"
        messages.append({
            "id": msg["id"],
            "subject": headers.get("Subject", ""),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "date": headers.get("Date", ""),
            "body": body,
            "attachments": _extract_attachments_meta(payload),
            "labels": msg.get("labelIds", []),
        })

    return {
        "thread_id": thread_id,
        "message_count": len(messages),
        "messages": messages,
    }


def get_attachment(creds: Credentials, message_id: str, attachment_id: str,
                   save_dir: Path, filename: str) -> Path:
    """Download an attachment to save_dir. Returns the saved path."""
    service = get_service(creds)
    att = _retry(lambda: service.users().messages().attachments().get(
        userId="me", messageId=message_id, id=attachment_id
    ).execute())

    data = base64.urlsafe_b64decode(att["data"])
    save_dir.mkdir(parents=True, exist_ok=True)
    # Prevent path traversal: keep basename only
    safe = Path(filename).name or "attachment.bin"
    dest = save_dir / safe
    # Avoid overwriting existing files
    counter = 1
    while dest.exists():
        stem, ext = os.path.splitext(safe)
        dest = save_dir / f"{stem} ({counter}){ext}"
        counter += 1
    dest.write_bytes(data)
    return dest


def _build_mime_message(to: str, subject: str, body: str, from_email: str,
                       cc: str = "", bcc: str = "",
                       in_reply_to: str = "", references: str = "",
                       attachments: list[Path] | None = None) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for path in attachments or []:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Attachment not found: {path}")
        ctype, encoding = mimetypes.guess_type(str(path))
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        data = path.read_bytes()
        if maintype == "text":
            part = MIMEText(data.decode("utf-8", errors="replace"), _subtype=subtype)
        elif maintype == "image":
            part = MIMEImage(data, _subtype=subtype)
        elif maintype == "audio":
            part = MIMEAudio(data, _subtype=subtype)
        elif maintype == "application":
            part = MIMEApplication(data, _subtype=subtype)
        else:
            part = MIMEBase(maintype, subtype)
            part.set_payload(data)
        part.add_header("Content-Disposition", "attachment", filename=path.name)
        msg.attach(part)

    return msg


def _encode_raw(mime_msg) -> str:
    return base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")


def create_draft(creds: Credentials, from_email: str, to: str, subject: str, body: str,
                 cc: str = "", bcc: str = "",
                 in_reply_to: str = "", references: str = "", thread_id: str = "",
                 attachments: list[Path] | None = None) -> dict:
    """Create a Gmail draft. Draft lives in Gmail until sent or discarded."""
    service = get_service(creds)
    mime = _build_mime_message(to, subject, body, from_email, cc, bcc,
                               in_reply_to, references, attachments)
    message_body = {"message": {"raw": _encode_raw(mime)}}
    if thread_id:
        message_body["message"]["threadId"] = thread_id

    draft = _retry(lambda: service.users().drafts().create(
        userId="me", body=message_body
    ).execute())
    return {
        "draft_id": draft["id"],
        "message_id": draft["message"]["id"],
        "thread_id": draft["message"].get("threadId"),
    }


def send_draft(creds: Credentials, draft_id: str) -> dict:
    """Send a previously-created draft."""
    service = get_service(creds)
    result = _retry(lambda: service.users().drafts().send(
        userId="me", body={"id": draft_id}
    ).execute())
    return {"message_id": result["id"], "thread_id": result.get("threadId"), "status": "sent"}


def discard_draft(creds: Credentials, draft_id: str) -> None:
    service = get_service(creds)
    _retry(lambda: service.users().drafts().delete(userId="me", id=draft_id).execute())


def list_drafts(creds: Credentials, max_results: int = 10) -> list[dict]:
    service = get_service(creds)
    result = _retry(lambda: service.users().drafts().list(
        userId="me", maxResults=max_results
    ).execute())
    drafts = result.get("drafts", [])
    out = []
    for d in drafts:
        detail = _retry(lambda did=d["id"]: service.users().drafts().get(
            userId="me", id=did, format="metadata"
        ).execute())
        headers = {h["name"]: h["value"] for h in detail.get("message", {}).get("payload", {}).get("headers", [])}
        out.append({
            "draft_id": d["id"],
            "subject": headers.get("Subject", "(no subject)"),
            "to": headers.get("To", ""),
            "snippet": detail.get("message", {}).get("snippet", "")[:100],
        })
    return out


def get_labels(creds: Credentials) -> list[dict]:
    service = get_service(creds)
    results = _retry(lambda: service.users().labels().list(userId="me").execute())
    return [
        {"id": l["id"], "name": l["name"], "type": l.get("type", "")}
        for l in results.get("labels", [])
    ]


def modify_labels(creds: Credentials, message_id: str,
                  add_labels: list[str] | None = None,
                  remove_labels: list[str] | None = None) -> dict:
    service = get_service(creds)
    body = {}
    if add_labels:
        body["addLabelIds"] = add_labels
    if remove_labels:
        body["removeLabelIds"] = remove_labels
    result = _retry(lambda: service.users().messages().modify(
        userId="me", id=message_id, body=body
    ).execute())
    return {"id": result["id"], "labels": result.get("labelIds", [])}


def trash_message(creds: Credentials, message_id: str) -> dict:
    """Move to trash (reversible for 30 days). Use instead of permanent delete."""
    service = get_service(creds)
    result = _retry(lambda: service.users().messages().trash(
        userId="me", id=message_id
    ).execute())
    return {"id": result["id"], "labels": result.get("labelIds", [])}
