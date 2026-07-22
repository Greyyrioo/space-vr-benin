"""
SpaceVRBenin -- Premium Gaming Center
Full-stack Flask application: public booking site + private admin control center.

Run:
    pip install -r requirements.txt
    cp .env.example .env      # fill in your SMTP + admin credentials
    python server.py

The app will be available at http://127.0.0.1:5000
Admin dashboard:            http://127.0.0.1:5000/admin
"""

import os
import re
import sqlite3
import random
import string
import json
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify, redirect,
    url_for, session, g, flash, send_file, Response
)
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------------

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "spacevr.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "spacevr-dev-secret-change-me")

# --- Mail configuration (Flask-Mail / SMTP) ---
app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "True") == "True"
app.config["MAIL_USE_SSL"] = os.environ.get("MAIL_USE_SSL", "False") == "True"
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get(
    "MAIL_DEFAULT_SENDER", os.environ.get("MAIL_USERNAME", "no-reply@spacevrbenin.local")
)
app.config["MAIL_SUPPRESS_SEND"] = os.environ.get("MAIL_USERNAME") in (None, "")

mail = Mail(app)

# --- Admin credentials ---
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get("ADMIN_PASSWORD", "spacevr123"))

# ---------------------------------------------------------------------------
# Static business data: zones + drinks bar menu
# ---------------------------------------------------------------------------

ZONES = {
    "vr-combat": {
        "name": "VR Combat Zone",
        "tagline": "Full-body tracked premium VR setups",
        "price_per_game": 3000.00,
        "games": [
            "Beat Saber", "Half-Life: Alyx", "Superhot VR",
            "Population: ONE", "Blade & Sorcery"
        ],
    },
    "racing-sim": {
        "name": "Racing Simulators",
        "tagline": "Force-feedback wheel rigs & motion seats",
        "price_per_game": 3000.00,
        "games": [
            "F1 23 Championship Rig", "Forza Motorsport",
            "Assetto Corsa Competizione", "Gran Turismo 7"
        ],
    },
    "ps5-hub": {
        "name": "PlayStation 5 Hub",
        "tagline": "Couch co-op and competitive gaming on the big screen",
        "price_per_game": 1000.00,
        "games": [
            "EA SPORTS FC 26", "Mortal Kombat 1", "Marvel's Spider-Man 2", "Elden Ring"
        ],
    },
    "table-tennis": {
        "name": "Table Tennis Zone",
        "tagline": "Fast-paced table tennis action with friends",
        "price_per_game": 1500.00,
        "games": ["Singles Match", "Doubles Showdown"],
    },
    "drinks-bar": {
        "name": "Drinks Bar",
        "tagline": "Refreshments delivered straight to your station",
        "price_per_game": 0.00,
        "games": [],
    },
}

FUEL_BAR_MENU = {
    "energy-drink": {"name": "Neon Surge Energy Drink", "price": 1500.00},
    "cola": {"name": "Ice-Cold Cola", "price": 1000.00},
    "water": {"name": "Bottled Water", "price": 500.00},
    "iso-sports": {"name": "Iso Sports Drink", "price": 1200.00},
    "chips": {"name": "Loaded Nacho Chips", "price": 1500.00},
    "candy-bar": {"name": "Choco Candy Bar", "price": 800.00},
    "pretzels": {"name": "Salted Pretzels", "price": 1000.00},
    "coffee": {"name": "Espresso Shot", "price": 1200.00},
}

BANK_DETAILS = {
    "bank_name": "OPay",
    "account_name": "SpaceVR Benin",
    "account_number": "8146497579",
    "reference_note": "Use your SVR booking reference as the transfer narration/description.",
}

DURATIONS_MIN = [1, 2, 3, 4, 5]

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_id TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            zone_id TEXT NOT NULL,
            zone_name TEXT NOT NULL,
            duration_min INTEGER NOT NULL,
            session_date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            drinks_json TEXT NOT NULL DEFAULT '[]',
            zone_cost REAL NOT NULL,
            drinks_cost REAL NOT NULL DEFAULT 0,
            total_cost REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending_payment',
            created_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            admin_reply TEXT,
            created_at TEXT NOT NULL,
            replied_at TEXT
        )
        """
    )
    db.commit()
    db.close()


# Ensure database tables exist on startup
init_db()

# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def generate_ref_id():
    """Generate a unique SVR-XXXX transaction reference."""
    db = get_db()
    while True:
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        ref = f"SVR-{suffix}"
        existing = db.execute(
            "SELECT 1 FROM bookings WHERE ref_id = ?", (ref,)
        ).fetchone()
        if not existing:
            return ref


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+\-\s()]{7,20}$")


def is_valid_email(value):
    return bool(value) and bool(EMAIL_RE.match(value.strip()))


def is_valid_phone(value):
    return bool(value) and bool(PHONE_RE.match(value.strip()))


def row_to_booking_dict(row):
    return {
        "id": row["id"],
        "ref_id": row["ref_id"],
        "customer_name": row["customer_name"],
        "phone": row["phone"],
        "email": row["email"],
        "zone_id": row["zone_id"],
        "zone_name": row["zone_name"],
        "duration_min": row["duration_min"],
        "session_date": row["session_date"],
        "time_slot": row["time_slot"],
        "drinks": json.loads(row["drinks_json"]),
        "zone_cost": row["zone_cost"],
        "drinks_cost": row["drinks_cost"],
        "total_cost": row["total_cost"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def row_to_ticket_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "phone": row["phone"],
        "subject": row["subject"],
        "message": row["message"],
        "status": row["status"],
        "admin_reply": row["admin_reply"],
        "created_at": row["created_at"],
        "replied_at": row["replied_at"],
    }


# ---------------------------------------------------------------------------
# Video Streaming Route (HTTP 206 Range Requests for Safari/iOS)
# ---------------------------------------------------------------------------

@app.route("/static/videos/<path:filename>")
def stream_video(filename):
    """Serve videos with HTTP 206 Partial Content range request support."""
    video_dir = os.path.join(app.root_path, "static", "videos")
    file_path = os.path.join(video_dir, filename)

    if not os.path.isfile(file_path):
        return "Video not found", 404

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("Range", None)

    if not range_header:
        return send_file(file_path, mimetype="video/mp4")

    match = re.search(r"bytes=(\d+)-(\d*)", range_header)
    if not match:
        return send_file(file_path, mimetype="video/mp4")

    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else file_size - 1

    if start >= file_size:
        return Response("Requested range not satisfiable", status=416)

    length = end - start + 1

    with open(file_path, "rb") as f:
        f.seek(start)
        data = f.read(length)

    response = Response(
        data,
        206,
        mimetype="video/mp4",
        content_type="video/mp4",
        direct_passthrough=True,
    )
    response.headers.add("Content-Range", f"bytes {start}-{end}/{file_size}")
    response.headers.add("Accept-Ranges", "bytes")
    response.headers.add("Content-Length", str(length))

    return response


# ---------------------------------------------------------------------------
# Email routing functions
# ---------------------------------------------------------------------------

def send_email_safe(subject, recipients, body_text, body_html=None):
    try:
        msg = Message(subject=subject, recipients=recipients, body=body_text, html=body_html)
        mail.send(msg)
        return True
    except Exception as exc:
        print(f"[MAIL ERROR] Could not send '{subject}' to {recipients}: {exc}")
        return False


def send_booking_received_email(booking):
    subject = f"SpaceVRBenin Booking Received -- {booking['ref_id']}"
    drinks_lines = "\n".join(
        f"  - {d['qty']} x {d['name']} (₦{d['line_total']:,.2f})" for d in booking["drinks"]
    ) or "  (none)"
    body = f"""Hi {booking['customer_name']},

We've received your SpaceVRBenin booking request. Here are the details:

Reference:   {booking['ref_id']}
Zone:        {booking['zone_name']}
Games:       {booking['duration_min']}
Date:        {booking['session_date']}
Time slot:   {booking['time_slot']}

Drinks Bar items:
{drinks_lines}

Zone cost:   ₦{booking['zone_cost']:,.2f}
Drinks cost: ₦{booking['drinks_cost']:,.2f}
TOTAL:       ₦{booking['total_cost']:,.2f}

To activate your station, please transfer the total amount to:

  Bank:            {BANK_DETAILS['bank_name']}
  Account name:    {BANK_DETAILS['account_name']}
  Account number:  {BANK_DETAILS['account_number']}
  Note:            {BANK_DETAILS['reference_note']}

Then bring a screenshot of your receipt or transfer confirmation to the
office counter to activate your station.

See you at SpaceVRBenin!
"""
    send_email_safe(subject, [booking["email"]], body)


def send_payment_confirmation_email(booking):
    subject = f"SpaceVRBenin Session Confirmed -- {booking['ref_id']}"
    body = f"""Hi {booking['customer_name']},

Good news -- your payment has been verified and your session is CONFIRMED.

Reference:  {booking['ref_id']}
Zone:       {booking['zone_name']}
Date:       {booking['session_date']}
Time slot:  {booking['time_slot']}
Games:      {booking['duration_min']}

Please arrive 10 minutes early with your reference code so we can get your
station ready. See you soon!

-- The SpaceVRBenin Team
"""
    send_email_safe(subject, [booking["email"]], body)


def send_ticket_reply_email(ticket):
    subject = f"SpaceVRBenin Support -- Re: {ticket['subject']}"
    body = f"""Hi {ticket['name']},

Thanks for reaching out to SpaceVRBenin support. Here's our response to your
message:

Your message:
  "{ticket['message']}"

Our reply:
  {ticket['admin_reply']}

If you have more questions, just reply to this email or send another
message through our website.

-- The SpaceVRBenin Team
"""
    send_email_safe(subject, [ticket["email"]], body)


# ---------------------------------------------------------------------------
# Auth decorator for admin routes
# ---------------------------------------------------------------------------

def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return render_template(
        "index.html",
        zones=ZONES,
        fuel_bar_menu=FUEL_BAR_MENU,
        durations=DURATIONS_MIN,
    )


@app.route("/api/zones")
def api_zones():
    return jsonify({"zones": ZONES, "fuel_bar_menu": FUEL_BAR_MENU, "durations": DURATIONS_MIN})


@app.route("/book", methods=["POST"])
def create_booking():
    data = request.get_json(force=True, silent=True) or {}

    customer_name = (data.get("customer_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip()
    zone_id = (data.get("zone_id") or "").strip()
    duration_min = data.get("duration_min")
    session_date = (data.get("session_date") or "").strip()
    time_slot = (data.get("time_slot") or "").strip()
    drink_selections = data.get("drinks") or []

    errors = []
    if len(customer_name) < 2:
        errors.append("Please enter your full name.")
    if not is_valid_phone(phone):
        errors.append("Please enter a valid phone number.")
    if not is_valid_email(email):
        errors.append("Please enter a valid email address.")
    if zone_id not in ZONES:
        errors.append("Please select a valid zone.")
    if duration_min not in DURATIONS_MIN:
        errors.append("Please select a valid number of games.")
    if not session_date:
        errors.append("Please select a session date.")
    if not time_slot:
        errors.append("Please select a time slot.")

    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    zone = ZONES[zone_id]
    zone_cost = round(zone["price_per_game"] * int(duration_min), 2)

    resolved_drinks = []
    drinks_cost = 0.0
    for item in drink_selections:
        item_id = item.get("item_id")
        qty = int(item.get("qty", 0))
        if item_id in FUEL_BAR_MENU and qty > 0:
            menu_item = FUEL_BAR_MENU[item_id]
            line_total = round(menu_item["price"] * qty, 2)
            drinks_cost += line_total
            resolved_drinks.append({
                "item_id": item_id,
                "name": menu_item["name"],
                "unit_price": menu_item["price"],
                "qty": qty,
                "line_total": line_total,
            })
    drinks_cost = round(drinks_cost, 2)
    total_cost = round(zone_cost + drinks_cost, 2)

    ref_id = generate_ref_id()
    created_at = datetime.utcnow().isoformat()

    db = get_db()
    db.execute(
        """
        INSERT INTO bookings (
            ref_id, customer_name, phone, email, zone_id, zone_name,
            duration_min, session_date, time_slot, drinks_json,
            zone_cost, drinks_cost, total_cost, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ref_id, customer_name, phone, email, zone_id, zone["name"],
            duration_min, session_date, time_slot, json.dumps(resolved_drinks),
            zone_cost, drinks_cost, total_cost, "pending_payment", created_at,
        ),
    )
    db.commit()

    row = db.execute("SELECT * FROM bookings WHERE ref_id = ?", (ref_id,)).fetchone()
    booking = row_to_booking_dict(row)

    send_booking_received_email(booking)

    return jsonify({"success": True, "booking": booking, "bank_details": BANK_DETAILS})


@app.route("/book/<ref_id>/mark-paid", methods=["POST"])
def mark_booking_paid(ref_id):
    db = get_db()
    row = db.execute("SELECT * FROM bookings WHERE ref_id = ?", (ref_id,)).fetchone()
    if not row:
        return jsonify({"success": False, "error": "Booking not found."}), 404

    if row["status"] == "pending_payment":
        db.execute(
            "UPDATE bookings SET status = ? WHERE ref_id = ?",
            ("awaiting_verification", ref_id),
        )
        db.commit()
        row = db.execute("SELECT * FROM bookings WHERE ref_id = ?", (ref_id,)).fetchone()

    booking = row_to_booking_dict(row)
    return jsonify({"success": True, "booking": booking})


@app.route("/receipt/<ref_id>")
def receipt(ref_id):
    db = get_db()
    row = db.execute("SELECT * FROM bookings WHERE ref_id = ?", (ref_id,)).fetchone()
    if not row:
        return render_template("receipt.html", booking=None, bank_details=BANK_DETAILS), 404
    booking = row_to_booking_dict(row)
    return render_template("receipt.html", booking=booking, bank_details=BANK_DETAILS)


@app.route("/api/receipt/<ref_id>")
def api_receipt(ref_id):
    db = get_db()
    row = db.execute("SELECT * FROM bookings WHERE ref_id = ?", (ref_id,)).fetchone()
    if not row:
        return jsonify({"success": False, "error": "Booking not found."}), 404
    return jsonify({"success": True, "booking": row_to_booking_dict(row), "bank_details": BANK_DETAILS})


@app.route("/support/ticket", methods=["POST"])
def create_support_ticket():
    data = request.get_json(force=True, silent=True) or {}

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    subject = (data.get("subject") or "").strip()
    message = (data.get("message") or "").strip()

    errors = []
    if len(name) < 2:
        errors.append("Please enter your name.")
    if not is_valid_email(email):
        errors.append("Please enter a valid email address.")
    if len(subject) < 2:
        errors.append("Please enter a subject.")
    if len(message) < 5:
        errors.append("Please enter your message.")

    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    created_at = datetime.utcnow().isoformat()
    db = get_db()
    cur = db.execute(
        """
        INSERT INTO tickets (name, email, phone, subject, message, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'open', ?)
        """,
        (name, email, phone, subject, message, created_at),
    )
    db.commit()
    ticket_row = db.execute("SELECT * FROM tickets WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify({"success": True, "ticket": row_to_ticket_dict(ticket_row)})


# ---------------------------------------------------------------------------
# Admin auth routes
# ---------------------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["is_admin"] = True
            session["admin_username"] = username
            next_url = request.args.get("next") or url_for("admin_dashboard")
            return redirect(next_url)
        error = "Invalid username or password."
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    session.pop("admin_username", None)
    return redirect(url_for("admin_login"))


# ---------------------------------------------------------------------------
# Admin dashboard routes
# ---------------------------------------------------------------------------

@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin.html", admin_username=session.get("admin_username"))


@app.route("/admin/api/bookings")
@admin_required
def admin_api_bookings():
    db = get_db()
    rows = db.execute("SELECT * FROM bookings ORDER BY created_at DESC").fetchall()
    bookings = [row_to_booking_dict(r) for r in rows]

    total_revenue = sum(b["total_cost"] for b in bookings if b["status"] == "confirmed")
    pending_verification = sum(1 for b in bookings if b["status"] == "awaiting_verification")
    pending_payment = sum(1 for b in bookings if b["status"] == "pending_payment")
    confirmed = sum(1 for b in bookings if b["status"] == "confirmed")

    return jsonify({
        "bookings": bookings,
        "stats": {
            "total_bookings": len(bookings),
            "confirmed": confirmed,
            "pending_verification": pending_verification,
            "pending_payment": pending_payment,
            "total_revenue": round(total_revenue, 2),
        },
    })


@app.route("/admin/api/bookings/<ref_id>/confirm", methods=["POST"])
@admin_required
def admin_confirm_booking(ref_id):
    db = get_db()
    row = db.execute("SELECT * FROM bookings WHERE ref_id = ?", (ref_id,)).fetchone()
    if not row:
        return jsonify({"success": False, "error": "Booking not found."}), 404

    db.execute("UPDATE bookings SET status = ? WHERE ref_id = ?", ("confirmed", ref_id))
    db.commit()
    row = db.execute("SELECT * FROM bookings WHERE ref_id = ?", (ref_id,)).fetchone()
    booking = row_to_booking_dict(row)
    send_payment_confirmation_email(booking)
    return jsonify({"success": True, "booking": booking})


@app.route("/admin/api/bookings/<ref_id>/cancel", methods=["POST"])
@admin_required
def admin_cancel_booking(ref_id):
    db = get_db()
    row = db.execute("SELECT * FROM bookings WHERE ref_id = ?", (ref_id,)).fetchone()
    if not row:
        return jsonify({"success": False, "error": "Booking not found."}), 404

    db.execute("UPDATE bookings SET status = ? WHERE ref_id = ?", ("cancelled", ref_id))
    db.commit()
    row = db.execute("SELECT * FROM bookings WHERE ref_id = ?", (ref_id,)).fetchone()
    return jsonify({"success": True, "booking": row_to_booking_dict(row)})


@app.route("/admin/api/tickets")
@admin_required
def admin_api_tickets():
    db = get_db()
    rows = db.execute("SELECT * FROM tickets ORDER BY created_at DESC").fetchall()
    tickets = [row_to_ticket_dict(r) for r in rows]
    open_count = sum(1 for t in tickets if t["status"] == "open")
    return jsonify({"tickets": tickets, "open_count": open_count})


@app.route("/admin/api/tickets/<int:ticket_id>/reply", methods=["POST"])
@admin_required
def admin_reply_ticket(ticket_id):
    data = request.get_json(force=True, silent=True) or {}
    reply_text = (data.get("reply") or "").strip()

    if len(reply_text) < 1:
        return jsonify({"success": False, "error": "Reply cannot be empty."}), 400

    db = get_db()
    row = db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        return jsonify({"success": False, "error": "Ticket not found."}), 404

    replied_at = datetime.utcnow().isoformat()
    db.execute(
        "UPDATE tickets SET admin_reply = ?, status = 'answered', replied_at = ? WHERE id = ?",
        (reply_text, replied_at, ticket_id),
    )
    db.commit()
    row = db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    ticket = row_to_ticket_dict(row)
    send_ticket_reply_email(ticket)
    return jsonify({"success": True, "ticket": ticket})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
