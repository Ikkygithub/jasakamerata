import asyncio
import ipaddress
import logging
import os
import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from core import db, new_id, now

log = logging.getLogger("email")
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_FROM_NAME = os.environ["EMAIL_FROM_NAME"]
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")
SITE = os.environ["PUBLIC_SITE_URL"].rstrip("/")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host):
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown, real):
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject, html):
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} ≠ real link host {real!r} (G3)")


async def send_email(*, to, subject, html):
    _assert_safe_email(subject, html)
    key = os.environ.get("EMERGENT_EMAIL_KEY", "").strip()
    if not key:
        return "disabled", "EMERGENT_EMAIL_KEY belum tersedia"
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    if EMAIL_REPLY_TO:
        payload["contact_email"] = EMAIL_REPLY_TO
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send", headers={"X-Email-Key": key}, json=payload)
        resp.raise_for_status()
        return "sent", resp.json().get("id", "")
    except httpx.HTTPStatusError as e:
        try:
            body = e.response.json()
        except ValueError:
            body = {}
        if body.get("code") in ("insufficient_credits", "integration_disabled", "daily_limit_reached"):
            log.warning("Email paused: %s: %s", body.get("code"), body.get("message", ""))
            return "paused", body.get("code")
        log.error("Email send failed: %s", e.response.status_code)
        return "failed", str(e.response.status_code)
    except Exception as e:  # noqa: BLE001
        log.error("Email send error: %s", e)
        return "failed", type(e).__name__


def _template(greeting, lines, cta_path, cta_label):
    items = "".join(f'<p style="margin:0 0 10px">{line}</p>' for line in lines)
    return (f'<table role="presentation" width="100%" style="background:#f4f4f0"><tr><td style="padding:28px">'
            f'<table role="presentation" width="100%" style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #e3e3dc">'
            f'<tr><td style="padding:28px;font-family:Arial,sans-serif;color:#222;font-size:14px;line-height:1.6">'
            f'<p style="font-size:18px;font-weight:bold;margin:0 0 18px">{escape(EMAIL_FROM_NAME)}</p>'
            f'<p style="margin:0 0 14px">{greeting}</p>{items}'
            f'<p style="margin:22px 0"><a href="{SITE}{cta_path}" style="background:#526b4a;color:#ffffff;padding:11px 18px;text-decoration:none">{escape(cta_label)}</a></p>'
            f'<p style="font-size:12px;color:#888;margin:18px 0 0">Email otomatis dari {escape(EMAIL_FROM_NAME)}, marketplace fotografer Makassar. '
            f'Kami tidak pernah meminta kata sandi, kode, atau data kartu melalui email.</p></td></tr></table></td></tr></table>')


_tasks = set()


async def _deliver(kind, ref, to, subject, html):
    try:
        status, detail = await send_email(to=to, subject=subject, html=html)
    except ValueError as e:
        status, detail = "blocked", str(e)[:200]
    await db.email_logs.insert_one({"log_id": new_id("eml"), "kind": kind, "ref": ref, "to": to, "subject": subject, "status": status, "detail": detail, "created_at": now()})


def queue(kind, ref, to, subject, html):
    if to:
        task = asyncio.create_task(_deliver(kind, ref, to, subject, html))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)


async def photographer_email(photographer_id):
    p = await db.photographers.find_one({"photographer_id": photographer_id}, {"user_id": 1})
    u = await db.users.find_one({"user_id": (p or {}).get("user_id", "-")}, {"email": 1, "name": 1})
    return u


async def notify_new_booking(b):
    u = await photographer_email(b["photographer_id"])
    if not u:
        return
    lines = [f"Paket: <b>{escape(b['service'])}</b>", f"Jadwal: {escape(b['date'])} pukul {escape(b['time'])} ({b['duration']} jam)", f"Lokasi: {escape(b['location'])}", f"Customer: {escape(b['customer_name'])}"]
    queue("booking_new", b["booking_id"], u["email"], f"Pesanan baru {b['booking_id']} di Jasakamerata", _template(f"Halo {escape(u.get('name', 'Fotografer'))}, ada permintaan pesanan baru untukmu.", lines, "/studio/pesanan", "Tinjau pesanan"))


async def notify_delivered(b):
    u = await db.users.find_one({"user_id": b["customer_id"]}, {"email": 1, "name": 1})
    if not u:
        return
    lines = [f"Pesanan <b>{escape(b['booking_id'])}</b> — {escape(b['service'])}", f"Fotografer: {escape(b['photographer_name'])}", "Silakan periksa hasilnya, lalu setujui, minta revisi, atau ajukan keberatan melalui halaman Pesanan Saya."]
    queue("booking_delivered", b["booking_id"], u["email"], f"Hasil foto pesanan {b['booking_id']} sudah diserahkan", _template(f"Halo {escape(u.get('name', 'Customer'))}, hasil layananmu sudah diserahkan.", lines, "/customer/pesanan", "Lihat hasil"))


async def notify_paid(b):
    u = await photographer_email(b["photographer_id"])
    if not u:
        return
    lines = [f"Pesanan <b>{escape(b['booking_id'])}</b> — {escape(b['service'])}", f"Jadwal: {escape(b['date'])} pukul {escape(b['time'])}", "Pembayaran telah terverifikasi oleh Midtrans. Silakan laksanakan sesi sesuai jadwal."]
    queue("booking_paid", b["booking_id"], u["email"], f"Pembayaran pesanan {b['booking_id']} terverifikasi", _template(f"Halo {escape(u.get('name', 'Fotografer'))}, pembayaran pesanan sudah diterima.", lines, "/studio/pesanan", "Buka pesanan"))
