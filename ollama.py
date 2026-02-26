#!/usr/bin/env python3
import json
import re
import urllib.request
import urllib.error
import pathlib
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlparse
HA_URL = "http://127.0.0.1:8123"
SECRETS = "/srv/homeassistant/secrets.yaml" #adjust your path
AGENT_ID = "your_conversation_id" #adjust this too
OUT_PATH = "/tmp/news_latest.txt" #rw folder
TTS_ENTITY = "tts.piper" #adjust this if doesnt matches
MEDIA_PLAYER = "media_player.home_assistant_voice_0xxxx_media_player" #adjust this 
TOKEN_KEY = "assist_button_token"
DEFAULT_RSS_URL = "https://hnrss.org/frontpage" #change if you want
DEFAULT_MAX_ITEMS = 12 # change if you want
def read_token() -> str:
    secrets_text = pathlib.Path(SECRETS).read_text(encoding="utf-8", errors="ignore")
    pattern = rf'^\s*{re.escape(TOKEN_KEY)}:\s*"?([^"\n]+)"?\s*$'
    m = re.search(pattern, secrets_text, re.MULTILINE)
    if not m:
        raise SystemExit(f"ERROR: Could not find {TOKEN_KEY} in {SECRETS}")
    return m.group(1).strip()
def normalize_rss_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return DEFAULT_RSS_URL
    if "://" not in raw:
        raw = "https://" + raw.lstrip("/")
    p = urlparse(raw)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise SystemExit("ERROR: Please enter a valid RSS URL (http/https).")
    return raw
def prompt_user_for_rss_url() -> str:
    print("\n=== News Briefing ===")
    print("Paste an RSS feed URL, or press Enter for default:")
    print(f"Default: {DEFAULT_RSS_URL}")
    try:
        rss = input("RSS URL: ")
    except KeyboardInterrupt:
        print("\nCancelled.")
        raise SystemExit(130)
    return normalize_rss_url(rss)
def prompt_user_for_max_items() -> int:
    try:
        raw = input(f"How many items? (default {DEFAULT_MAX_ITEMS}): ").strip()
    except KeyboardInterrupt:
        print("\nCancelled.")
        raise SystemExit(130)
    if not raw:
        return DEFAULT_MAX_ITEMS
    try:
        n = int(raw)
    except ValueError:
        raise SystemExit("ERROR: Please enter a number.")
    if n < 1 or n > 50:
        raise SystemExit("ERROR: Please choose a number between 1 and 50.")
    return n
def fetch_rss(rss_url: str, max_items: int) -> str:
    with urllib.request.urlopen(rss_url, timeout=30) as r:
        xml_data = r.read()
    root = ET.fromstring(xml_data)
    channel = root.find("channel")
    if channel is None:
        channel = root.find(".//channel")
    if channel is None:
        raise SystemExit("ERROR: This does not look like an RSS feed (no channel found).")
    feed_title = (channel.findtext("title") or "News Feed").strip()
    items = channel.findall("item")
    if not items:
        items = channel.findall(".//item")
    items = items[:max_items]
    lines = []
    lines.append(f"{feed_title} 
 latest headlines")
    lines.append(f"Feed: {rss_url}")
    lines.append(f"Fetched: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    for i, it in enumerate(items, start=1):
        it_title = (it.findtext("title") or "").strip() or "(no title)"
        it_link = (it.findtext("link") or "").strip()
        it_pub = (
            (it.findtext("pubDate") or "")
            or (it.findtext("{http://purl.org/dc/elements/1.1/}date") or "")
        ).strip()
        if it_pub:
            lines.append(f"{i}. {it_title} ({it_pub})")
        else:
            lines.append(f"{i}. {it_title}")
        if it_link:
            lines.append(f"   {it_link}")
        lines.append("")
    text = "\n".join(lines).strip() + "\n"
    pathlib.Path(OUT_PATH).write_text(text, encoding="utf-8")
    return text
def ha_post(path: str, token: str, payload: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        f"{HA_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code} calling {path}:\n{body}")
    except Exception as e:
        raise SystemExit(f"ERROR calling {path}: {e!r}")
def build_prompt(provided_text: str) -> str:
    return (
        "IMPORTANT:\n"
        "- You are NOT being asked to browse the web.\n"
        "- You DO have access to the full text below (it is provided in this message).\n"
        "- Do NOT say you lack access to external content/news/feeds.\n"
        "- Do NOT request the user to provide the content (it is already provided).\n"
        "- Use ONLY the text between BEGIN PROVIDED TEXT and END PROVIDED TEXT.\n\n"
        "TASK:\n"
        "Create a short spoken news briefing from the headlines.\n"
        "- Do NOT read URLs.\n"
        "- Keep it under ~90 seconds spoken.\n"
        "- Prefer 5
8 short sentences.\n\n"
        "BEGIN PROVIDED TEXT\n"
        f"{provided_text}\n"
        "END PROVIDED TEXT\n"
    )
def main() -> None:
    token = read_token()
    rss_url = prompt_user_for_rss_url()
    max_items = prompt_user_for_max_items()
    print("\nFetching RSS...")
    provided_text = fetch_rss(rss_url, max_items)
    print("Generating briefing (Ollama Server)...")
    prompt = build_prompt(provided_text)
    resp = ha_post(
        "/api/conversation/process",
        token,
        {"text": prompt, "language": "en", "agent_id": AGENT_ID},
        timeout=180,
    )
    speech = (
        resp.get("response", {})
        .get("speech", {})
        .get("plain", {})
        .get("speech", "")
    ).strip()
    if not speech:
        raise SystemExit(f"ERROR: No speech returned:\n{json.dumps(resp, indent=2)}")
    print("\n=== Briefing (will be spoken) ===")
    print(speech)
    print("================================")
    ha_post(
        "/api/services/tts/speak",
        token,
        {"entity_id": TTS_ENTITY, "media_player_entity_id": MEDIA_PLAYER, "message": speech},
        timeout=60,
    )
    print("\nOK: Spoken on Voice Preview.")
    print(f"(Saved fetched headlines to {OUT_PATH})")
if __name__ == "__main__":
    main()
