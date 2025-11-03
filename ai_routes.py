from flask import Blueprint, request, jsonify
import os, json, time
from ai_classifier import classify, CATEGORIES

# ---------------------------------------------
# JSON Database Setup
# ---------------------------------------------
ROOT = os.path.dirname(__file__)
DB_FILE = os.path.join(ROOT, "gschool.json")
ai = Blueprint("ai", __name__, url_prefix="/api/ai")

# ---------------------------------------------
# Helper functions
# ---------------------------------------------
def _load_db():
    if not os.path.exists(DB_FILE):
        return {"categories": {}, "settings": {}, "chat_messages": []}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"categories": {}, "settings": {}, "chat_messages": []}

def _save_db(data):
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def ensure_schema():
    db = _load_db()
    # seed categories if missing
    if "categories" not in db:
        db["categories"] = {}
    for c in CATEGORIES:
        if c not in db["categories"]:
            db["categories"][c] = {"blocked": False, "block_url": None}
    if "settings" not in db:
        db["settings"] = {}
    if "chat_messages" not in db:
        db["chat_messages"] = []
    _save_db(db)

def get_setting(key, default=None):
    db = _load_db()
    return db.get("settings", {}).get(key, default)

def set_setting(key, value):
    db = _load_db()
    db.setdefault("settings", {})[key] = value
    _save_db(db)

# ---------------------------------------------
# Routes
# ---------------------------------------------
@ai.route("/categories", methods=["GET", "POST"])
def categories():
    ensure_schema()
    db = _load_db()

    if request.method == "POST":
        body = request.json or {}
        name = body.get("name")
        if not name:
            return jsonify({"ok": False, "error": "name required"}), 400
        blocked = bool(body.get("blocked"))
        block_url = body.get("block_url")
        db["categories"][name] = {"blocked": blocked, "block_url": block_url}
        _save_db(db)
        return jsonify({"ok": True})
    else:
        cats = [{"name": n, **v} for n, v in sorted(db["categories"].items())]
        return jsonify({"ok": True, "categories": cats})

# ---------------------------------------------
# AI Classifier
# ---------------------------------------------
@ai.route("/classify", methods=["POST"])
def api_classify():
    ensure_schema()
    body = request.json or {}
    url = body.get("url") or ""
    html = body.get("html")
    result = classify(url, html)

    db = _load_db()
    cat_data = db.get("categories", {}).get(result["category"], {"blocked": False, "block_url": None})
    blocked = bool(cat_data.get("blocked"))
    cat_block_url = cat_data.get("block_url")

    default_redirect = get_setting("blocked_redirect", "https://blocked.gdistrict.org/Gschool%20block")
    final_block_url = cat_block_url or default_redirect
    return jsonify({"ok": True, "url": url, "result": result, "blocked": blocked, "block_url": final_block_url})

# ---------------------------------------------
# Simple Chat System
# ---------------------------------------------
@ai.route("/chat/send", methods=["POST"])
def chat_send():
    ensure_schema()
    b = request.json or {}
    room = b.get("room") or "*"
    user_id = b.get("user_id") or "unknown"
    role = b.get("role") or "student"
    text = (b.get("text") or "").strip()[:1000]
    if not text:
        return jsonify({"ok": False, "error": "empty"}), 400

    ts = int(time.time() * 1000)
    db = _load_db()
    db.setdefault("chat_messages", []).append({
        "room": room,
        "user_id": user_id,
        "role": role,
        "text": text,
        "ts": ts
    })
    _save_db(db)
    return jsonify({"ok": True, "ts": ts})

@ai.route("/chat/poll", methods=["GET"])
def chat_poll():
    ensure_schema()
    room = request.args.get("room", "*")
    since = int(request.args.get("since", "0") or 0)
    db = _load_db()
    msgs = [m for m in db.get("chat_messages", []) if m["room"] == room and m["ts"] > since]
    return jsonify({"ok": True, "messages": msgs})
