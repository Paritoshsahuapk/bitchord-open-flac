import os
import re
import time
from urllib.parse import quote

import requests
from flask import Flask, jsonify, request, Response

app = Flask(__name__)

ARCHIVE_SEARCH = "https://archive.org/advancedsearch.php"
ARCHIVE_METADATA = "https://archive.org/metadata/"
USER_AGENT = "BitChord-Hybrid-FLAC-Addon/1.0 (personal music search)"
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "300"))
_cache = {}

MANIFEST = {
    "id": "in.paritosh.bitchord.archive-flac",
    "name": "Open FLAC Search",
    "version": "1.0.0",
    "description": "Searches Internet Archive for playable FLAC recordings. Commercial catalogue coverage is limited.",
    "resources": ["search", "stream"],
    "allowDownloads": 1,
    "settings": [
        {
            "key": "quality",
            "type": "select",
            "default": "lossless",
            "options": [
                {"label": "Lossless", "value": "lossless"},
                {"label": "High", "value": "high"},
                {"label": "Low", "value": "low"}
            ]
        }
    ]
}

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def cached(key, fetch):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]
    value = fetch()
    _cache[key] = (now, value)
    return value


def clean_text(value):
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value if v)
    return re.sub(r"\s+", " ", str(value or "")).strip()


def archive_files(identifier):
    def fetch():
        response = session.get(
            ARCHIVE_METADATA + quote(identifier, safe=""),
            timeout=12
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("files", [])
    return cached("meta:" + identifier, fetch)


def flac_file(files):
    candidates = []
    for item in files:
        name = str(item.get("name", ""))
        if name.lower().endswith(".flac") and not item.get("private"):
            size = item.get("size")
            try:
                size = int(size)
            except (TypeError, ValueError):
                size = 0
            candidates.append((size, name))
    # Prefer the largest FLAC file when an item contains multiple variants.
    candidates.sort(reverse=True)
    return candidates[0][1] if candidates else None


def search_archive(query, limit):
    # Internet Archive advanced search is a public search API. Restrict results
    # to audio items and inspect metadata before advertising a FLAC result.
    q = f'mediatype:audio AND ({query})'
    params = {
        "q": q,
        "fl[]": ["identifier", "title", "creator", "date"],
        "rows": min(max(limit * 3, 10), 60),
        "page": 1,
        "output": "json",
        "sort[]": "downloads desc"
    }
    response = session.get(ARCHIVE_SEARCH, params=params, timeout=12)
    response.raise_for_status()
    return response.json().get("response", {}).get("docs", [])


@app.get("/")
def root():
    return jsonify(MANIFEST)


@app.get("/manifest.json")
def manifest():
    return jsonify(MANIFEST)


@app.get("/health")
@app.get("/healthz")
def health():
    return jsonify({"ok": True, "service": MANIFEST["id"]})


@app.get("/search")
def search():
    query = clean_text(request.args.get("q", ""))
    if not query:
        return jsonify({"tracks": [], "total": 0})
    limit = min(max(request.args.get("limit", default=20, type=int), 1), 30)

    try:
        docs = search_archive(query, limit)
        tracks = []
        seen = set()
        for doc in docs:
            identifier = clean_text(doc.get("identifier"))
            title = clean_text(doc.get("title"))
            if not identifier or not title or identifier in seen:
                continue
            seen.add(identifier)
            try:
                filename = flac_file(archive_files(identifier))
            except (requests.RequestException, ValueError, KeyError):
                continue
            if not filename:
                continue

            artist = clean_text(doc.get("creator"))
            tracks.append({
                "id": identifier,
                "title": title,
                "artist": artist or "Unknown artist",
                "album": "",
                "duration": 0,
                "format": "flac",
                "audioQuality": "LOSSLESS",
                "artworkURL": (
                    "https://archive.org/services/img/" + quote(identifier, safe="")
                )
            })
            if len(tracks) >= limit:
                break

        return jsonify({"tracks": tracks, "total": len(tracks)})
    except requests.RequestException:
        return jsonify({"tracks": [], "total": 0, "error": "Internet Archive search is temporarily unavailable"}), 502


@app.get("/stream/<path:identifier>")
def stream(identifier):
    # IDs are validated against Archive metadata; no arbitrary URL proxying.
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,200}", identifier):
        return jsonify({"error": "Invalid recording identifier"}), 400
    try:
        filename = flac_file(archive_files(identifier))
        if not filename:
            return jsonify({"error": "No FLAC file is available for this recording"}), 404
        url = (
            "https://archive.org/download/"
            + quote(identifier, safe="")
            + "/"
            + quote(filename, safe="/")
        )
        return jsonify({
            "url": url,
            "format": "flac",
            "quality": "FLAC lossless (source file)",
            "codec": "flac",
            "container": "flac",
            "manifest": "none",
            "encrypted": False
        })
    except requests.RequestException:
        return jsonify({"error": "Could not resolve this recording right now"}), 502


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "Not found"}), 404


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
