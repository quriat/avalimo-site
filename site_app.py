#!/usr/bin/env python3
import os
import sys
import uuid
import json
import smtplib
import threading
from email.mime.text import MIMEText
import datetime as _dt
import pytz
import time
import re
import pickle
import base64
import urllib.request
from flask import Flask, request, jsonify, render_template_string, redirect
import openai

try:
    import requests as _req
except ImportError:
    _req = None

try:
    from square.client import Square, SquareEnvironment
except ImportError:
    Square = None

app = Flask(__name__)

_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for _line in f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                k, _, v = _line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

SQ_APP_ID = os.environ.get("SQUARE_APPLICATION_ID", "sandbox-sq0idb-fake")
SQ_LOCATION_ID = os.environ.get("SQUARE_LOCATION_ID", "Lfake")
SQ_TOKEN = os.environ.get("SQUARE_ACCESS_TOKEN", "")
SQ_ENV = os.environ.get("SQUARE_ENVIRONMENT", "sandbox")
AV_API_KEY = os.environ.get("AVIATIONSTACK_KEY", "")
GA_ID = os.environ.get("GA_ID", "G-STY7CSKRMX")
SC_ID = os.environ.get("SC_ID", "")
FB_PIXEL_ID = os.environ.get("FB_PIXEL_ID", "")
GOOGLE_SHEETS_URL = os.environ.get("GOOGLE_SHEETS_WEBHOOK_URL", "")

SC_META = f'<meta name="google-site-verification" content="{SC_ID}" />' if SC_ID else ""
FB_PIXEL = f'''<!-- Meta Pixel -->
<script>
!function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
fbq('init','{FB_PIXEL_ID}');fbq('track','PageView');
</script>
<noscript><img height="1" width="1" style="display:none" src="https://www.facebook.com/tr?id={FB_PIXEL_ID}&ev=PageView&noscript=1" /></noscript>''' if FB_PIXEL_ID else ""

_blog_path = os.path.join(os.path.dirname(__file__), "blog_posts.json")
BLOG_POSTS = json.load(open(_blog_path)) if os.path.exists(_blog_path) else []

_PAGE_CONTENT_PATH = os.path.join(os.path.dirname(__file__), "page_content.json")
PAGE_CONTENT = json.load(open(_PAGE_CONTENT_PATH)) if os.path.exists(_PAGE_CONTENT_PATH) else {}


def send_booking_email(data: dict):
    name = data.get("name", "?")
    phone = data.get("phone", "?")
    pickup = data.get("pickup", "?")
    dropoff = data.get("dropoff", "?")
    time = data.get("time", "?")
    vehicle = data.get("vehicle", "?")
    pax = data.get("pax", "1")
    notes = data.get("notes", "")
    service = data.get("service", "")
    flight = data.get("flight", "")
    email = data.get("email", "")

    lines = [f"New Booking from {name}"]
    lines.append(f"Phone: {phone}")
    if email:
        lines.append(f"Email: {email}")
    lines.append(f"Service: {service or 'Not specified'}")
    lines.append(f"Vehicle: {vehicle}")
    lines.append(f"Passengers: {pax}")
    lines.append(f"Pickup: {pickup}")
    lines.append(f"Dropoff: {dropoff}")
    lines.append(f"Time: {time}")
    if flight:
        lines.append(f"Flight: {flight}")
    if notes:
        lines.append(f"Notes: {notes}")

    body = "\n".join(lines)
    print("\n" + "=" * 50)
    print(body)
    print("=" * 50 + "\n")

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

    smtp_user = os.environ.get("SMTP_USERNAME", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    email_to = os.environ.get("EMAIL_TO", "adam@avalimo.net")

    if not smtp_user or not smtp_pass:
        print("SMTP not configured — booking logged to stdout only")
        return

    try:
        msg = MIMEText(body)
        msg["From"] = smtp_user
        msg["To"] = email_to
        msg["Subject"] = f"New AvaLimo Booking — {name}"

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        print(f"Booking email sent to {email_to}")
    except Exception as e:
        print(f"Failed to send email: {e}")


def send_contact_email(data: dict):
    name = data.get("name", "?")
    email = data.get("email", "?")
    phone = data.get("phone", "?")
    subject = data.get("subject", "General Inquiry")
    message = data.get("message", "")

    body = f"Contact Inquiry from {name}\nEmail: {email}\nPhone: {phone}\nSubject: {subject}\n\nMessage:\n{message}"
    print("\n" + "=" * 50)
    print(body)
    print("=" * 50 + "\n")

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

    smtp_user = os.environ.get("SMTP_USERNAME", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    email_to = os.environ.get("EMAIL_TO", "adam@avalimo.net")

    if not smtp_user or not smtp_pass:
        print("SMTP not configured — contact inquiry logged to stdout only")
        return

    try:
        msg = MIMEText(body)
        msg["From"] = smtp_user
        msg["To"] = email_to
        msg["Subject"] = f"AvaLimo Contact — {subject} from {name}"
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        print(f"Contact email sent to {email_to}")
    except Exception as e:
        print(f"Failed to send contact email: {e}")


def log_to_google_sheets(sheet_name: str, data: dict):
    url = GOOGLE_SHEETS_URL
    if not url:
        return
    try:
        payload = json.dumps({"sheet": sheet_name, "data": data})
        req = urllib.request.Request(
            url,
            data=payload.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"Google Sheets ({sheet_name}) — status {resp.status}")
    except Exception as e:
        print(f"Google Sheets log failed ({sheet_name}): {e}")


# ── Read old index.html as Jinja2 template ──────────────────────────────
_INDEX_PATH = os.path.join(os.path.dirname(__file__), "index.html")
BASE_HTML = open(_INDEX_PATH, encoding="utf-8").read() if os.path.exists(_INDEX_PATH) else "<h1>Site under construction</h1>"


PAGE_META = {
    "": { "title": "AvaLimo — Houston Premier Limo Service | IAH & Hobby Airport Transfers", "desc": "Houston's most trusted chauffeur service. Airport transfers for IAH & Hobby, corporate travel, weddings & events — 24/7, zero surge pricing. Book online.", "og_type": "website", "og_image": "https://avalimo.net/og-image.jpg" },
    "services": { "title": "Services — AvaLimo | Houston Limo & Chauffeur Service", "desc": "Airport transfers, corporate travel, wedding limo, event transportation & more. Houston's premium chauffeur service — 24/7.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
    "fleet": { "title": "Our Fleet — AvaLimo | Luxury Sedans, SUVs & Sprinter Vans", "desc": "Mercedes S-Class, Cadillac Escalade & Mercedes Sprinter. Houston's finest luxury fleet for any occasion.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
    "book": { "title": "Book a Ride — AvaLimo | Online Reservation", "desc": "Reserve your Houston luxury chauffeur service online in 30 seconds. Airport transfers, corporate & events — 24/7.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
    "blog": { "title": "Blog — AvaLimo | Houston Limo Service Insights & Tips", "desc": "Expert guides on Houston airport transfers, wedding limo tips, corporate travel, and luxury transportation. Daily articles from Houston's premier chauffeur service.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
    "flight-status": { "title": "Flight Status — AvaLimo | Real-Time Flight Tracker", "desc": "Track your flight in real-time. Free flight status tool for IAH, Hobby & all airlines.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
    "contact": { "title": "Contact — AvaLimo | Houston Limo Service", "desc": "Get in touch with AvaLimo. Call (832) 917-6331 (AI) or (832) 567-8050 (dispatch). 24/7.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
    "faq": { "title": "FAQ — AvaLimo | Frequently Asked Questions", "desc": "Answers to common questions about booking, pricing, cancellations & more.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
    "policy": { "title": "Policy — AvaLimo | Company Policy", "desc": "AvaLimo company policy: booking, cancellation, refund & privacy terms.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
    "deposit": { "title": "Pay Online — AvaLimo | Secure Payment Portal", "desc": "Pay your deposit or balance online. Secure Square payment portal for AvaLimo reservations.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
    "pricing": { "title": "Limo Rental Cost Houston — AvaLimo Pricing", "desc": "Transparent flat-rate pricing for Houston limo service. S-Class $100/hr, Escalade $120/hr, Sprinter $180/hr + 20% gratuity. No surge fees.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
    "wedding-limo": { "title": "Wedding Limo Houston — AvaLimo | Luxury Wedding Transportation", "desc": "Houston wedding limo service. Mercedes S-Class, Cadillac Escalade & Sprinter for your special day.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
    "prom-limo": { "title": "Prom Limo Houston — AvaLimo | Safe Prom Transportation 2026", "desc": "Prom limo service in Houston. Safe, stylish prom transportation for groups up to 14.", "og_type": "website", "og_image": "https://avalimo.net/static/mercedes_sprinter.png" },
    "quinceanera-limo": { "title": "Quinceañera Limo Houston — AvaLimo | Quince Transportation", "desc": "Quinceañera limo service in Houston. Luxury transportation for your quince celebration.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
    "corporate-transportation": { "title": "Corporate Transportation Houston — AvaLimo | Executive Car Service", "desc": "Corporate transportation in Houston. Executive car service for business meetings, airport transfers & client entertainment.", "og_type": "website", "og_image": "https://avalimo.net/static/mercedes_sclass.png" },
    "airport-iah": { "title": "IAH Airport Limo Service | Flat Rates, Flight Tracking, 24/7 | AvaLimo", "desc": "Premium IAH airport transfers from $95. Real-time flight tracking, meet & greet at all 5 terminals, no surge fees. Book online or call (832) 567-8050.", "og_type": "website", "og_image": "https://avalimo.net/og-image.jpg" },
    "airport-hobby": { "title": "Hobby Airport Limo Service — AvaLimo | HOU Airport Transfers", "desc": "Hobby airport limo service in Houston. Professional chauffeurs, flight tracking & flat rates.", "og_type": "website", "og_image": "https://avalimo.net/static/mercedes_sclass.png" },
    "airport-24-7-service": { "title": "24/7 Airport Car Service Houston — AvaLimo | Anytime Transfers", "desc": "24-hour airport car service in Houston. Early morning, late night & anytime transfers from IAH & Hobby.", "og_type": "website", "og_image": "https://avalimo.net/static/mercedes_sclass.png" },
    "black-car-service": { "title": "Black Car Service Houston — AvaLimo | Premium Chauffeur Service", "desc": "Professional black car service in Houston. Mercedes S-Class, Cadillac Escalade.", "og_type": "website", "og_image": "https://avalimo.net/static/mercedes_sclass.png" },
    "chauffeur-service": { "title": "Chauffeur Service Houston — AvaLimo | Private Driver Service", "desc": "Professional chauffeur service in Houston. Private driver for airport, corporate, wedding & event transportation.", "og_type": "website", "og_image": "https://avalimo.net/static/mercedes_sclass.png" },
    "party-bus": { "title": "Party Bus Rental Houston — AvaLimo | Group Party Transportation", "desc": "Party bus rental in Houston. Mercedes Sprinter with ambient lighting, premium sound & BYOB-friendly.", "og_type": "website", "og_image": "https://avalimo.net/static/mercedes_sprinter.png" },
    "event-transportation": { "title": "Event Transportation Houston — AvaLimo | Concert & Event Service", "desc": "Event transportation in Houston. Concerts, galas, sports games & special events.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
    "bachelorette-party": { "title": "Bachelorette Party Bus Houston — AvaLimo | Bride Tribe Transport", "desc": "Bachelorette party transportation in Houston. BYOB-friendly Sprinter vans for the bride tribe.", "og_type": "website", "og_image": "https://avalimo.net/static/mercedes_sprinter.png" },
    "galveston-cruise-transport": { "title": "Galveston Cruise Port Transportation — AvaLimo | Cruise Limo Service", "desc": "Galveston cruise port transportation from Houston. Premium limo service to cruise terminals.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
    "wine-tours": { "title": "Texas Hill Country Wine Tour from Houston — AvaLimo | Wine Tours", "desc": "Texas Hill Country wine tour transportation from Houston. Mercedes Sprinter wine tours to Fredericksburg & beyond.", "og_type": "website", "og_image": "https://avalimo.net/static/mercedes_sprinter.png" },
    "new-years-eve-limo": { "title": "New Year's Eve Limo Houston — AvaLimo | NYE Transportation", "desc": "New Year's Eve limo service in Houston. No surge pricing, flat-rate NYE transportation.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
    "fleet/mercedes-s-class": { "title": "Mercedes S-Class Rental Houston — AvaLimo Fleet", "desc": "Book the Mercedes S-Class in Houston for airport transfers, weddings & corporate travel.", "og_type": "website", "og_image": "https://avalimo.net/static/mercedes_sclass.png" },
    "fleet/cadillac-escalade": { "title": "Cadillac Escalade Rental Houston — AvaLimo Fleet", "desc": "Book the Cadillac Escalade in Houston for airport transfers, weddings & corporate travel.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
    "fleet/mercedes-sprinter": { "title": "Mercedes Sprinter Rental Houston — AvaLimo Fleet", "desc": "Book the Mercedes Sprinter in Houston for group transportation, wine tours & weddings.", "og_type": "website", "og_image": "https://avalimo.net/static/mercedes_sprinter.png" },
    "locations/galveston": { "title": "Galveston Limo Service — AvaLimo | Island Transportation", "desc": "Galveston limo service from Houston. Cruise port transfers, beach weddings & island getaways.", "og_type": "website", "og_image": "https://avalimo.net/static/cadillac_escalade.png" },
}

PAGE_H1 = {
    "": 'Houston\'s Finest <span class="gold">Limo Service</span>',
    "services": 'Houston <span class="gold">Chauffeur Services</span>',
    "fleet": 'Our <span class="gold">Luxury Fleet</span>',
    "book": 'Book Your <span class="gold">AvaLimo Ride</span>',
    "blog": 'AvaLimo <span class="gold">Blog & Tips</span>',
    "flight-status": 'Real-Time <span class="gold">Flight Status</span>',
    "contact": 'Contact <span class="gold">AvaLimo</span>',
    "faq": 'Frequently Asked <span class="gold">Questions</span>',
    "policy": 'AvaLimo <span class="gold">Company Policy</span>',
    "deposit": 'Secure <span class="gold">Online Payment</span>',
}


@app.route("/robots.txt")
def robots_txt():
        return "User-agent: *\nAllow: /\nSitemap: https://avalimo.net/sitemap.xml", 200, {"Content-Type": "text/plain"}

@app.route("/og-image.jpg")
def og_image():
        import flask as _flask
        _path = os.path.join(os.path.dirname(__file__), "static", "og-image.jpg")
        if os.path.exists(_path):
                return _flask.send_file(_path, mimetype="image/jpeg", max_age=86400)
        return ("not found", 404)

@app.route("/sitemap.xml")
def sitemap_xml():
        # Clean sitemap: only URLs that serve the new SPA design and return 200.
        # Old landing pages now 301 to SPA sections, so they are intentionally excluded.
        _today = _dt.date.today().isoformat()
        home = '<url><loc>https://avalimo.net/</loc><lastmod>{}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>'.format(_today)
        policy = '<url><loc>https://avalimo.net/policy</loc><lastmod>{}</lastmod><changefreq>yearly</changefreq><priority>0.3</priority></url>'.format(_today)
        blog_urls = "\n".join(f'<url><loc>https://avalimo.net/blog/{p["slug"]}</loc><lastmod>{_today}</lastmod><changefreq>weekly</changefreq><priority>0.6</priority></url>' for p in sorted(BLOG_POSTS, key=_post_date_key, reverse=True) if p.get("slug"))
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    {home}
    {blog_urls}
    {policy}
    </urlset>'''
        return xml, 200, {"Content-Type": "application/xml"}


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def index(path):
    meta = None
    featured_post = None
    page_h1 = 'Houston\'s Finest <span class="gold">Limo Service</span>'
    canonical_path = ""
    og_type = "website"
    og_image = "https://avalimo.net/og-image.jpg"
    content_key = path

    legacy_redirects = {
        "company-policy": "policy",
        "terms-and-conditions": "policy",
        "cancellation-policy": "policy",
        "book-your-ride": "book",
        "booking-confirmed": "book",
        "pay-deposit": "deposit",
        "houston-airport-limo-service": "",
        "houston-airport": "",
        "sugar-land-limo": "",
        "sugar-land": "",
        "the-woodlands-limo": "",
        "the-woodlands": "",
        "katy-limo": "",
        "katy": "",
        "missouri-city-limo": "",
        "missouri-city": "",
        "pearland-limo": "",
        "pearland": "",
        "galveston-limo": "",
        "galveston": "",
        "league-city-limo": "",
        "league-city": "",
        "baytown-limo": "",
        "baytown": "",
        "spring-limo": "",
        "spring": "",
        "cypress-limo": "",
        "cypress": "",
    }
    if path in legacy_redirects:
        target = legacy_redirects[path]
        return redirect(f"/{target}" if target else "/", 301)

    if path.startswith("blog/") and len(path) > 5:
        slug = path[5:]
        for p in BLOG_POSTS:
            if p.get("slug") == slug:
                meta = {"title": p["title"] + " — AvaLimo", "desc": p.get("summary", "")}
                canonical_path = f"/blog/{slug}"
                og_type = "article"
                og_image = f"https://avalimo.net{p.get('image', '/static/cadillac_escalade.png')}"
                content_key = "blog"
                featured_post = p
                safe_title = p["title"].replace("<", "&lt;").replace(">", "&gt;")
                page_h1 = f'{safe_title}'
                break
        if meta is None:
            content_key = "404"
    elif path in PAGE_CONTENT:
        meta = {"title": PAGE_CONTENT[path]["title"], "desc": PAGE_CONTENT[path]["desc"]}
        canonical_path = f"/{path}"
        og_type = "website"
        og_image = "https://avalimo.net/og-image.jpg"
        content_key = "page"
    elif path in PAGE_META:
        meta = PAGE_META[path]
        canonical_path = f"/{path}" if path else ""
        page_h1 = PAGE_H1.get(path, page_h1)
    else:
        content_key = "404"

    if meta is None:
        meta = {"title": "Page Not Found — AvaLimo", "desc": "Sorry, the page you requested could not be found."}
        canonical_path = ""
        og_type = "website"
        og_image = "https://avalimo.net/og-image.jpg"
        page_h1 = 'Page Not Found'

    canonical_url = f"https://avalimo.net{canonical_path}"

    # Build blog posts HTML for injection
    blog_cards = ""
    for i, post in enumerate(BLOG_POSTS):
        delay_style = f' style="transition-delay:{post.get("delay", "0s")}"' if post.get("delay") and post.get("delay") != "0s" else ""
        blog_cards += f"""<div class="blog-card fade-up" data-slug="{post['slug']}"{delay_style}>
        <div class="thumb">{post.get('emoji', '&#128663;')}</div>
        <div class="body">
          <div class="cat">{post.get('cat', '')}</div>
          <h3>{post['title']}</h3>
          <p>{post.get('summary', '')[:150]}...</p>
          <a href="/blog/{post['slug']}" class="btn btn-outline" style="padding:8px 20px;font-size:12px">Read More</a>
          <div class="meta"><span>{post.get('date', '')}</span><span>&#8226; {post.get('read', '')}</span></div>
          <div class="article-content">{post.get('content', '')}</div>
        </div>
      </div>"""

    # BlogPosting schema for rich snippets
    def _blog_schema(post):
        return {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": post.get("title", ""),
            "description": post.get("summary", ""),
            "author": {"@type": "Person", "name": post.get("author", "AvaLimo")},
            "datePublished": post.get("date", ""),
            "dateModified": post.get("date", ""),
            "image": "https://avalimo.net" + post.get("image", "/static/chauffeur_service.png"),
            "publisher": {"@type": "Organization", "name": "AvaLimo",
                          "logo": {"@type": "ImageObject", "url": "https://avalimo.net/static/chauffeur_service.png"}},
            "mainEntityOfPage": {"@type": "WebPage", "@id": f"https://avalimo.net/blog/{post.get('slug', '')}"},
            "articleBody": re.sub("<[^>]+>", "", post.get("content", "")),
        }

    if featured_post:
        blog_schema = f'<script type="application/ld+json">{json.dumps(_blog_schema(featured_post), ensure_ascii=False)}</script>'
    elif content_key == "blog":
        item_list = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "url": f"https://avalimo.net/blog/{p.get('slug', '')}"}
                for i, p in enumerate(BLOG_POSTS)
            ],
        }
        blog_schema = f'<script type="application/ld+json">{json.dumps(item_list, ensure_ascii=False)}</script>'
    else:
        blog_schema = ""

    rendered = render_template_string(
        BASE_HTML,
        title=meta["title"],
        meta_desc=meta["desc"],
        canonical_url=canonical_url,
        og_type=og_type,
        og_image=og_image,
        ga_id=GA_ID,
        sc_meta=SC_META,
        fb_pixel=FB_PIXEL,
        sq_app_id=SQ_APP_ID,
        sq_location_id=SQ_LOCATION_ID,
        blog_posts_html=blog_cards,
        featured_post=featured_post,
        content_key=content_key,
        page_content_html=PAGE_CONTENT.get(path, {}).get("content", "") if content_key == "page" else "",
        blog_schema=blog_schema,
        page_h1=page_h1,
    )
    status_code = 404 if content_key == "404" else 200
    resp = app.make_response((rendered, status_code))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    resp.headers["X-Version"] = "v2.0-video-gloss"
    return resp


def _fire_n8n_reminder(data):
    url = os.environ.get("N8N_BOOKING_WEBHOOK", "")
    if not url:
        return
    try:
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"n8n reminder webhook — status {resp.status}")
    except Exception as e:
        print(f"n8n reminder webhook failed: {e}")


def _fire_n8n_review(data):
    url = os.environ.get("N8N_REVIEW_WEBHOOK", "")
    if not url:
        return
    try:
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"n8n review webhook — status {resp.status}")
    except Exception as e:
        print(f"n8n review webhook failed: {e}")


def _post_date_key(p):
    """Parse a blog post's mixed-format date into a sortable date (newest-first)."""
    s = str(p.get("date", "")).strip()
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%B %Y", "%b %Y"):
        try:
            return _dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    try:
        return _dt.date.fromisoformat(s[:10])
    except Exception:
        return _dt.date(1970, 1, 1)


@app.route("/api/blog")
def api_blog():
    """Blog posts for the React homepage & blog index page (newest first)."""
    limit = request.args.get("limit", "4")
    posts = [
        {
            "slug": p.get("slug", ""),
            "title": p.get("title", ""),
            "summary": p.get("summary", ""),
            "date": p.get("date", ""),
        }
        for p in sorted(BLOG_POSTS, key=_post_date_key, reverse=True)
        if p.get("slug")
    ]
    if limit != "all":
        try:
            posts = posts[: max(1, int(limit))]
        except ValueError:
            posts = posts[:4]
    return jsonify({"status": "ok", "posts": posts})


@app.route("/api/blog/<slug>")
def api_blog_post(slug):
    """Full blog post content for the React blog reader."""
    post = next((p for p in BLOG_POSTS if p.get("slug") == slug), None)
    if not post:
        return jsonify({"status": "error", "message": "Post not found"}), 404
    return jsonify({"status": "ok", "post": {
        "slug": post.get("slug", ""),
        "title": post.get("title", ""),
        "summary": post.get("summary", ""),
        "content": post.get("content", ""),
        "date": post.get("date", ""),
    }})


GOOGLE_PLACES_API_KEY = (
    os.environ.get("GOOGLE_PLACES_API_KEY")
    or os.environ.get("GOOGLE_MAPS_API_KEY")
    or os.environ.get("GOOGLE_API_KEY")
    or ""
)
GOOGLE_PLACE_ID = os.environ.get("GOOGLE_PLACE_ID", "ChIJSZpoR7TvQIYRWBRoVXu3j7w")
_REVIEWS_CACHE = os.path.join(os.path.dirname(__file__), "reviews_cache.json")
_REVIEWS_TTL = 6 * 3600  # refresh every 6h
print(f"[reviews] GOOGLE_PLACES_API_KEY configured: {bool(GOOGLE_PLACES_API_KEY)} (place={GOOGLE_PLACE_ID})", file=sys.stderr, flush=True)


def _rel_time(iso_ts):
    try:
        dt = _dt.datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        days = max(0, (_dt.datetime.now(_dt.timezone.utc) - dt).days)
    except Exception:
        return ""
    if days <= 0:
        return "Today"
    if days == 1:
        return "1 day ago"
    if days < 7:
        return f"{days} days ago"
    if days < 30:
        return f"{days // 7} week{'s' if days // 7 > 1 else ''} ago"
    if days < 365:
        return f"{days // 30} month{'s' if days // 30 > 1 else ''} ago"
    return f"{days // 365} year{'s' if days // 365 > 1 else ''} ago"


def _normalize_google_reviews(data):
    out = []
    for i, r in enumerate(data.get("reviews") or []):
        attr = r.get("authorAttribution") or {}
        author = attr.get("displayName") or "Google user"
        text = ((r.get("text") or {}).get("text") or "").strip()
        if not text:
            continue
        item = {
            "id": f"g-{i}-{abs(hash(author + text)) % 100000}",
            "author": author,
            "rating": r.get("rating", 5),
            "date": r.get("relativePublishTimeDescription") or _rel_time(r.get("publishTime", "")) or "Recent",
            "comment": text,
            "avatarUrl": attr.get("photoUri"),
            "authorUrl": attr.get("uri"),
            "tripType": "Google Review",
            "verifiedTrip": False,
            "helpfulCount": 0,
            "hasLeftOnGoogle": True,
            "source": "google",
        }
        out.append(item)
    return out


def _fetch_google_reviews():
    if not GOOGLE_PLACES_API_KEY:
        return None
    url = f"https://places.googleapis.com/v1/places/{GOOGLE_PLACE_ID}"
    field_mask = ",".join([
        "displayName",
        "rating",
        "userRatingCount",
        "reviews.authorAttribution.displayName",
        "reviews.authorAttribution.photoUri",
        "reviews.authorAttribution.uri",
        "reviews.rating",
        "reviews.text",
        "reviews.relativePublishTimeDescription",
        "reviews.publishTime",
    ])
    headers = {"X-Goog-Api-Key": GOOGLE_PLACES_API_KEY, "X-Goog-FieldMask": field_mask}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"Google Places fetch failed: {e}")
        return None


@app.route("/api/reviews")
def api_reviews():
    """Latest real Google reviews (Places API), cached to disk."""
    fresh = None
    try:
        if os.path.exists(_REVIEWS_CACHE):
            cached = json.load(open(_REVIEWS_CACHE))
            if time.time() - cached.get("_ts", 0) < _REVIEWS_TTL:
                fresh = cached
    except Exception:
        fresh = None

    if fresh is None:
        data = _fetch_google_reviews()
        if data is not None:
            fresh = {
                "_ts": time.time(),
                "reviews": _normalize_google_reviews(data),
                "rating": data.get("rating"),
                "count": data.get("userRatingCount"),
            }
            try:
                json.dump(fresh, open(_REVIEWS_CACHE, "w"))
            except Exception:
                pass
        elif os.path.exists(_REVIEWS_CACHE):
            try:
                fresh = json.load(open(_REVIEWS_CACHE))
            except Exception:
                fresh = None

    if not fresh:
        return jsonify({
            "status": "unconfigured",
            "reviews": [],
            "debug": {"key_present": bool(GOOGLE_PLACES_API_KEY), "place_id": GOOGLE_PLACE_ID},
        })
    return jsonify({
        "status": "ok",
        "reviews": fresh.get("reviews", []),
        "rating": fresh.get("rating"),
        "count": fresh.get("count"),
    })


@app.route("/api/book", methods=["POST"])
def book_ride():
    data = request.get_json() or {}
    send_booking_email(data)
    log_to_google_sheets("Bookings", data)
    threading.Thread(target=_fire_n8n_reminder, args=(data,), daemon=True).start()
    threading.Thread(target=_fire_n8n_review, args=(data,), daemon=True).start()
    return jsonify({"status": "ok", "message": "Booking received! We'll confirm your ride shortly."})


@app.route("/api/contact", methods=["POST"])
def contact():
    data = request.get_json() or {}
    send_contact_email(data)
    log_to_google_sheets("Contacts", data)
    return jsonify({"status": "ok", "message": "Message sent! We'll get back to you shortly."})


@app.route("/api/flight")
def flight_track():
    q = request.args.get("q", "").upper().strip().replace(" ", "")
    if not q:
        return jsonify({"status": "error", "message": "No flight number provided"}), 400

    if AV_API_KEY:
        try:
            import requests as req
            resp = req.get("https://api.aviationstack.com/v1/flights", params={
                "access_key": AV_API_KEY, "flight_iata": q
            }, timeout=10)
            data = resp.json()
            candidates = data.get("data") or []
            # Codeshare filtering: keep only records whose flight iata matches the query
            # exactly (feeds return partner-operated duplicates like SN8919/LX3356 for UA2217).
            def _matches_q(f):
                return (f.get("flight") or {}).get("iata", "").upper() == q
            exact = [f for f in candidates if _matches_q(f)]
            pool = exact or candidates
            # Only trust flights that actually involve Houston.
            houston_cands = [f for f in pool
                             if (f.get("arrival") or {}).get("iata") in ("IAH", "HOU")
                             or (f.get("departure") or {}).get("iata") in ("IAH", "HOU")]
            best = next((f for f in houston_cands
                         if (f.get("arrival") or {}).get("iata") in ("IAH", "HOU")), None) or (houston_cands[0] if houston_cands else None)
            if best:
                f = best
                dep = f.get("departure", {})
                arr = f.get("arrival", {})
                status = f.get("flight_status", "unknown")
                gate = arr.get("gate") or dep.get("gate") or "—"
                term = arr.get("terminal") or dep.get("terminal") or "—"
                d_iata = dep.get("iata") or "?"
                a_iata = arr.get("iata") or "?"
                houston_tz = pytz.timezone("America/Chicago")
                def _fmt_local(iso_str):
                    """Convert ISO timestamp to Houston local HH:MM."""
                    if not iso_str:
                        return ""
                    try:
                        dt = _dt.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
                        if dt.tzinfo is None:
                            dt = pytz.utc.localize(dt)
                        return dt.astimezone(houston_tz).strftime("%H:%M")
                    except (ValueError, TypeError):
                        return iso_str.split("T")[1][:5] if "T" in iso_str else ""
                est = arr.get("estimated") or arr.get("scheduled") or ""
                est = _fmt_local(est)
                sched_arr = _fmt_local(arr.get("scheduled") or "")
                sched = _fmt_local(dep.get("scheduled") or "")
                delay = dep.get("delay") or 0
                return jsonify({
                    "flight": q, "airline": f.get("airline", {}).get("name", "?"),
                    "route": f"{d_iata} → {a_iata}",
                    "sched": sched, "est": est, "sched_arr": sched_arr,
                    "delay_minutes": delay,
                    "status": status,
                    "gate": gate, "term": term
                })
            else:
                return jsonify({"status": "error", "message": f"No data for flight {q}"}), 404
        except Exception as e:
            return jsonify({"status": "error", "message": f"API error: {e}"}), 502
    else:
        return jsonify({"status": "error", "message": "Flight tracking API key not configured. Add AVIATIONSTACK_KEY to your .env"}), 503


@app.route("/api/deposit", methods=["POST"])
def process_deposit():
    data = request.get_json() or {}
    amount = data.get("amount", "0")
    email = data.get("email", "")
    name = data.get("name", "")

    print(f"\n{'='*50}")
    print(f"Deposit request: ${amount} from {name} ({email})")
    print(f"{'='*50}\n")

    return jsonify({
        "status": "ok",
        "message": f"Deposit of ${amount} received! Your booking is secured.",
        "amount": amount,
    })


@app.route("/api/square-pay", methods=["POST"])
def square_pay():
    data = request.get_json() or {}
    source_id = data.get("source_id", "")
    amount_cents = data.get("amount", 0)
    name = data.get("name", "")
    email = data.get("email", "")

    if not source_id:
        return jsonify({"status": "error", "message": "Missing payment source."}), 400
    if not amount_cents or amount_cents < 50:
        return jsonify({"status": "error", "message": "Minimum deposit is $0.50."}), 400

    print(f"\n{'='*50}")
    print(f"Square payment request: ${amount_cents/100:.2f} from {name} ({email})")

    if not Square or not SQ_TOKEN:
        print("Square SDK not configured — payment simulated")
        print(f"{'='*50}\n")
        return jsonify({
            "status": "ok",
            "message": "Payment authorized (demo mode). Set SQUARE_ACCESS_TOKEN in .env for live payments.",
            "payment_id": "sim_" + uuid.uuid4().hex[:12],
        })

    try:
        env = SquareEnvironment.SANDBOX if SQ_ENV == "sandbox" else SquareEnvironment.PRODUCTION
        client = Square(token=SQ_TOKEN, environment=env)
        result = client.payments.create(
            source_id=source_id,
            idempotency_key=uuid.uuid4().hex,
            amount_money={"amount": amount_cents, "currency": "USD"},
            buyer_email_address=email or None,
            note=f"AvaLimo deposit from {name}",
            reference_id="deposit",
        )

        if result.is_success():
            pid = result.body["payment"]["id"]
            status = result.body["payment"]["status"]
            print(f"  Payment {pid} — {status}")
            print(f"{'='*50}\n")
            return jsonify({"status": "ok", "message": f"Payment {status}. ID: {pid}", "payment_id": pid})
        else:
            errs = result.errors or []
            detail = errs[0]["detail"] if errs else "Payment declined"
            print(f"  Payment failed: {detail}")
            print(f"{'='*50}\n")
            return jsonify({"status": "error", "message": detail}), 402

    except Exception as e:
        print(f"  Square error: {e}")
        print(f"{'='*50}\n")
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Calendar Reminder Scheduler ────────────────────────────────────────

_NOTIFIED_EVENTS: set = set()


def _ensure_google_files():
    for var, name in [("GOOGLE_CREDENTIALS_B64", "credentials.json"),
                      ("GOOGLE_TOKEN_B64", "token.json")]:
        val = os.environ.get(var)
        if val:
            path = os.path.join(os.path.dirname(__file__), name)
            if not os.path.exists(path):
                with open(path, "wb") as f:
                    f.write(base64.b64decode(val))


def _send_textbelt_sms(phone: str, message: str):
    key = os.environ.get("TEXTBELT_KEY", "textbelt")
    payload = json.dumps({"phone": phone, "message": message, "key": key}).encode()
    try:
        req = urllib.request.Request(
            "https://textbelt.com/text",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
        if result.get("success"):
            print(f"SMS sent to {phone} (quota: {result.get('quotaRemaining', '?')})", file=sys.stderr, flush=True)
        else:
            print(f"SMS failed to {phone}: {result.get('error', 'unknown')}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"SMS error for {phone}: {e}", file=sys.stderr, flush=True)


def _check_calendar_reminders():
    try:
        from google.auth.transport.requests import Request as GAuthReq
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        print("Google API libs not installed — calendar reminders disabled", file=sys.stderr, flush=True)
        return

    creds_file = os.path.join(os.path.dirname(__file__), "credentials.json")
    token_file = os.path.join(os.path.dirname(__file__), "token.json")
    if not os.path.exists(creds_file):
        print("credentials.json not found — calendar reminders disabled", file=sys.stderr, flush=True)
        return

    creds = None
    if os.path.exists(token_file):
        with open(token_file, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(GAuthReq())
            except Exception as e:
                print(f"Calendar token refresh failed: {e}", file=sys.stderr, flush=True)
                return
        else:
            print("Calendar not authenticated — run locally to re-auth", file=sys.stderr, flush=True)
            return
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)

    try:
        service = build("calendar", "v3", credentials=creds)
    except Exception as e:
        print(f"Calendar build failed: {e}", file=sys.stderr, flush=True)
        return

    now = _dt.datetime.now(_dt.timezone.utc)
    tomorrow_start = (now + _dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = tomorrow_start + _dt.timedelta(days=1)

    try:
        events = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=tomorrow_start.isoformat(),
                timeMax=tomorrow_end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
    except Exception as e:
        print(f"Calendar fetch failed: {e}", file=sys.stderr, flush=True)
        return

    for ev in events.get("items", []):
        eid = ev.get("id", "")
        if eid in _NOTIFIED_EVENTS:
            continue
        summary = (ev.get("summary") or "").strip()
        description = (ev.get("description") or "")
        start = ev.get("start", {})

        phone = ""
        phone_match = re.search(r"(?:Phone|phone|PHONE)\s*[:=]\s*([+\d\s\-()]+)", description)
        if phone_match:
            phone = phone_match.group(1).strip()
            phone = "+" + re.sub(r"[^\d]", "", phone[1:]) if phone.startswith("+") else re.sub(r"[^\d]", "", phone)
            if phone and len(phone) < 10:
                phone = ""

        if not phone:
            print(f"Skipping '{summary}' — no phone number in description", file=sys.stderr, flush=True)
            continue

        pickup_str = ""
        if "dateTime" in start:
            dt = _dt.datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
            pickup_str = dt.strftime("%I:%M %p")

        pickup_loc = ""
        loc_match = re.search(r"(?:Pickup|pickup|PICKUP)\s*(?::|=)\s*(.+)", description)
        if loc_match:
            pickup_loc = loc_match.group(1).strip()
        if not pickup_loc:
            pickup_loc = ev.get("location", "")

        msg = (
            f"Hi {summary}, this is AvaLimo confirming your "
            f"{'pickup at ' + pickup_loc + ' ' if pickup_loc else ''}"
            f"tomorrow at {pickup_str}. "
            f"Reply or call (832) 917-6331 for changes."
        )
        _send_textbelt_sms(phone, msg)
        _NOTIFIED_EVENTS.add(eid)
        print(f"Reminder SMS sent for '{summary}' to {phone}", file=sys.stderr, flush=True)


def _reminder_loop():
    while True:
        try:
            _check_calendar_reminders()
        except Exception as e:
            print(f"Reminder check error: {e}", file=sys.stderr, flush=True)
        time.sleep(3600)


_ensure_google_files()
threading.Thread(target=_reminder_loop, daemon=True).start()
print("Calendar reminder scheduler started", file=sys.stderr, flush=True)


# ─── AI Chat Endpoint ───
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if OPENAI_API_KEY:
    try:
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
    except Exception as _e:
        print(f"OpenAI client init failed — chat disabled: {_e}", file=sys.stderr, flush=True)
        openai_client = None
else:
    print("OPENAI_API_KEY not set — chat endpoint disabled", file=sys.stderr, flush=True)
    openai_client = None

CHAT_SYSTEM_PROMPT = """You are the AvaLimo AI Assistant for AvaLimo, Houston's premier luxury limousine service.

BUSINESS INFO:
- Company: AvaLimo
- Phone: (832) 917-6331
- Website: avalimo.net
- Location: Houston, TX
- Hours: 24/7 service

SERVICES:
- Airport Transfers (IAH & Hobby)
- Corporate/Business Travel
- Weddings & Special Events
- Night Out/Prom
- Concerts & Sports Events
- Wine Tours
- Bachelor/Bachelorette Parties
- Hourly Charters

FLEET & PRICING:
- Mercedes S-Class (sedan): 1-3 passengers, Starting $45/hr or $100 flat rate
- Cadillac Escalade (SUV): 1-6 passengers, Starting $65/hr or $125 flat rate
- Mercedes Sprinter (van): 1-14 passengers, Starting $150/hr or $250 flat rate

COMMON ROUTES (Flat Rates):
- IAH to Galleria: $65
- IAH to Downtown: $60
- IAH to Katy: $75
- IAH to The Woodlands: $70
- IAH to Sugar Land: $80
- IAH to Medical Center: $65
- HOU to Galleria: $50
- HOU to Downtown: $45
- HOU to Medical Center: $45
- HOU to Katy: $65
- Downtown to Galleria: $35
- Houston to Galveston: $175
- Houston to Austin: $450
- Houston to San Antonio: $500

SERVICE AREAS:
Houston, Katy, Sugar Land, The Woodlands, Memorial, River Oaks, Galleria, Downtown, Heights, Midtown, Museum District, Texas Medical Center, Bellaire, West University, Pearland, Friendswood, League City, Galveston

BOOKING:
- Online: avalimo.net/book
- Phone: (832) 917-6331
- Minimum 2-hour advance recommended
- Same-day bookings available (call to check)

PAYMENT:
- Credit cards accepted (Visa, MC, Amex, Discover)
- Corporate accounts available
- Gratuity not included (18-20% suggested)

POLICIES:
- Cancellation: 24 hours notice for full refund
- Late cancellation: 50% charge
- No-show: Full charge
- Overtime: 1.5x hourly rate
- Waiting time: 15 min grace period, then $1/min

RULES:
- Be helpful, professional, and friendly
- Give specific quotes when possible
- Always offer to help book or connect with dispatch
- Keep responses concise
"""

@app.route("/api/chat", methods=["POST"])
def chat():
    if openai_client is None:
        return jsonify({"status": "error", "message": "AI chat is temporarily unavailable. Please call dispatch at (832) 567-8050."}), 503
    data = request.json
    messages = data.get("messages", [])
    full_messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + messages
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=full_messages,
            max_tokens=500,
            temperature=0.7
        )
        reply = response.choices[0].message.content
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5002
    print(f"AvaLimo site running on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)