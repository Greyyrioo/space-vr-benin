# SpaceVRBenin — Premium Gaming Center

A full-stack booking site + private admin control center for a VR/gaming lounge.

## Stack

- **Backend:** Python, Flask, Flask-Mail, SQLite (via the standard `sqlite3` module — no extra DB server needed)
- **Frontend:** Server-rendered Jinja2 templates + modular vanilla CSS/JS (no build step required)

## Project layout

```
spacevr/
├── server.py                # All routes, booking logic, email routing, admin API
├── requirements.txt
├── .env.example             # Copy to .env and fill in real values
├── spacevr.db                # Created automatically on first run
├── templates/
│   ├── index.html            # Public site: hero, arsenal, booking + checkout modals
│   ├── receipt.html          # Standalone digital receipt page
│   ├── admin_login.html      # Admin sign-in
│   └── admin.html            # Admin control center (bookings + support tickets)
└── static/
    ├── css/
    │   ├── style.css          # Public site theme
    │   └── admin.css          # Admin dashboard theme
    ├── js/
    │   ├── main.js            # Zone modals, Fuel Bar quantity selector, booking + checkout
    │   └── admin.js           # Admin dashboard data fetching + actions
    └── images/                # Drop your own photos here (see naming below)
```

## Setup

```bash
cd spacevr
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with your admin password and SMTP credentials
python server.py
```

Visit `http://127.0.0.1:5000` for the public site and
`http://127.0.0.1:5000/admin` for the control center
(default login is whatever you set as `ADMIN_USERNAME` / `ADMIN_PASSWORD` in `.env`).

If you don't configure SMTP credentials in `.env`, the app still runs completely —
emails are simply printed to the console instead of being sent, so you can test
the entire booking flow with zero external setup.

## Swapping in your own photos

Drop files into `static/images/` using these exact names and the site will
pick them up automatically (a stock photo shows as a fallback until you do):

- `bg-parallax.jpg` — global parallax background (recommend 1920×1080+)
- `gallery1.jpg` … `gallery6.jpg` — gallery section photos
- `testimonial1.jpg`, `testimonial2.jpg`, `testimonial3.jpg` — reviewer avatars

To use your own written reviews, edit the three `.testimonial-card` blocks
directly inside `templates/index.html`.

## Editing zones, prices & the Fuel Bar menu

All business data — zone names, hourly prices, game lists, and Fuel Bar items
with prices — lives in one place at the top of `server.py`, in the `ZONES`
and `FUEL_BAR_MENU` dictionaries. Pricing is always calculated server-side
from these dictionaries, never trusted from the browser, so it can't be
tampered with by a customer.

## Editing the bank transfer details

Update the `BANK_DETAILS` dictionary in `server.py` with your real bank
account information — it's rendered on both the checkout screen and the
confirmation email.

## Booking → payment → receipt flow

1. Customer picks a zone (and optionally adds Fuel Bar items) and submits the
   booking form → `POST /book` creates a `pending_payment` row and emails the
   customer the bank details.
2. Customer taps **"I've Completed The Transfer"** → `POST /book/<ref>/mark-paid`
   moves the booking to `awaiting_verification` and shows `/receipt/<ref>`.
3. Staff check the bank account, find the matching transfer, and click
   **Confirm** in `/admin` → the booking becomes `confirmed` and a
   confirmation email goes out automatically.

## Support tickets

Any message submitted through the "Talk To The Team" form on the public site
becomes a ticket visible in `/admin` under **Support Tickets**. Typing a reply
there and clicking **Send Reply By Email** emails that response straight to
the customer's inbox and marks the ticket **Answered**.
