#!/usr/bin/env python3
"""Generate one useful AvaLimo article and update blog_posts.json atomically."""

import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://168.231.74.172:32792/api/chat")
MODELS = [
    name.strip()
    for name in os.getenv(
        "OLLAMA_MODELS",
        "deepseek-v4-flash:cloud,qwen3.5:cloud,minimax-m3:cloud",
    ).split(",")
    if name.strip()
]
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
BLOG_FILE = os.path.join(REPO_DIR, "blog_posts.json")

CATEGORIES = ["Airport Travel", "Travel Tips", "Weddings", "Corporate", "Events", "Fleet"]
EMOJIS = {
    "Airport Travel": "&#9992;",
    "Travel Tips": "&#127542;",
    "Weddings": "&#128141;",
    "Corporate": "&#127963;",
    "Events": "&#127796;",
    "Fleet": "&#128664;",
}


def _extract_json(text: str) -> dict:
    """Accept raw JSON or a fenced/prefixed JSON object from a model."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    start = text.find("{")
    if start < 0:
        raise ValueError("model response did not contain a JSON object")
    value, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(value, dict):
        raise ValueError("model response was not a JSON object")
    return value


def _request_post(model: str, category: str, today: str) -> dict:
    prompt = f"""Write one original, people-first AvaLimo article for Houston travelers.
Category: {category}
Length: 650-900 words.

Requirements:
- Give practical, Houston-specific advice based on stable facts (IAH, Hobby, Houston traffic, luggage, pickup planning, group size, accessibility, or event logistics as relevant).
- Do not invent customer counts, awards, exact travel times, live events, vehicle features, prices, licenses, reviews, or safety claims.
- Use a descriptive title, a concise summary, and useful HTML with <p>, <h2>, <ul>, and <li> tags.
- Add one natural link to /book and one relevant link to /services, /fleet, /pricing, or /contact.
- End with a helpful booking call to action, not keyword stuffing.
- Avoid repeating generic phrases such as "arrive in style" or "ultimate luxury."

Return ONLY valid JSON with these exact keys:
title, summary, content, date ("{today}"), read (for example "5 min read").
No markdown fences or explanation."""
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False}
    ).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
    response = json.loads(urllib.request.urlopen(req, timeout=180).read())
    if response.get("error"):
        raise RuntimeError(response["error"])
    return _extract_json(response["message"]["content"])


def generate_post() -> dict:
    category = CATEGORIES[date.today().toordinal() % len(CATEGORIES)]
    today = date.today().isoformat()
    errors = []
    for index, model in enumerate(MODELS):
        try:
            post = _request_post(model, category, today)
            for field in ("title", "summary", "content", "date", "read"):
                if not isinstance(post.get(field), str) or not post[field].strip():
                    raise ValueError(f"missing or invalid field: {field}")
            post["date"] = today
            post["emoji"] = EMOJIS[category]
            post["cat"] = category
            post["slug"] = re.sub(r"[^a-z0-9]+", "-", post["title"].lower()).strip("-")
            return post
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, KeyError, RuntimeError) as exc:
            errors.append(f"{model}: {exc}")
            if index + 1 < len(MODELS):
                time.sleep(10)
    raise RuntimeError("all blog models failed: " + " | ".join(errors))


def main() -> None:
    with open(BLOG_FILE, encoding="utf-8") as source:
        posts = json.load(source)
    new = generate_post()
    if any(post.get("slug") == new["slug"] for post in posts):
        new["slug"] = f'{new["slug"]}-{new["date"]}'
    posts.insert(0, new)

    fd, temporary_path = tempfile.mkstemp(prefix="blog-posts-", suffix=".json", dir=REPO_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            json.dump(posts, target, indent=2, ensure_ascii=False)
            target.write("\n")
        os.replace(temporary_path, BLOG_FILE)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)
    print(f'Generated: {new["title"]}')


if __name__ == "__main__":
    main()
