#!/usr/bin/env python3
import json
import re
import sys
import time
import pathlib
import urllib.request
import urllib.error

HA_URL = "http://127.0.0.1:8123"
SECRETS = "/srv/homeassistant/secrets.yaml" # adjust your path

TOKEN_KEY = "assist_button_token"
LUMO_URL = "http://127.0.0.1:3333"

TTS_ENTITY = "tts.piper" #adjust your tts
MEDIA_PLAYER = "media_player.home_assistant_voice_0xxxx_media_player" #adjust your plyer


PROMPT_ENTITY = "input_text.lumo_prompt"


def read_token() -> str:
    txt = pathlib.Path(SECRETS).read_text(encoding="utf-8", errors="ignore")
    m = re.search(
        rf'^\s*{re.escape(TOKEN_KEY)}:\s*"?([^"\n]+)"?\s*$',
        txt,
        re.MULTILINE,
    )
    if not m:
        raise SystemExit(f"ERROR: {TOKEN_KEY} not found in {SECRETS}")
    return m.group(1).strip()


def ha_get_state(token: str, entity_id: str) -> str:
    req = urllib.request.Request(
        f"{HA_URL}/api/states/{entity_id}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"ERROR: HA GET state HTTP {e.code}\n{body}")
    return (data.get("state") or "").strip()


def http_post_json(url: str, payload: dict, timeout: int = 120) -> tuple[int, dict, bytes]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def parse_response(status: int, headers: dict, body: bytes) -> str:
    raw = body.decode("utf-8", errors="replace").strip()
    ct = (headers.get("Content-Type", "") or "").lower()

    if status != 200:
        raise SystemExit(f"ERROR: Lumo HTTP {status}\n{raw}")

    if "application/json" in ct:
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                for k in ("text", "response", "answer", "message", "output"):
                    v = obj.get(k)
                    if isinstance(v, str) and v.strip():
                        return v.strip()
            return json.dumps(obj, ensure_ascii=False)
        except Exception:
            return raw

    return raw


def clean_lumo_text(text: str) -> str:
    if not text:
        return ""

    lines = [ln.strip() for ln in text.splitlines()]
    out: list[str] = []

    drop_exact = {
        "Edit",
        "Ask anything to Lumo",
        "Upload",
        "Web search",
        "Press Enter to ask",
        "Regenerate",
        "Favorite",
        "Current chat:",
        "About",
        "By Proton",
        "For Business",
        "Sources",
        "5 results",
        "[]",
        "I like this response",
        "Report an issue",
        "Conversation encrypted",
        "Lumo can make mistakes. Please double-check responses.",
        "This message is empty. Sorry about that.",
        "Something went wrong",
        "Your request didn't go through or couldn't be completed. Try sending it again.",
    }

    for ln in lines:
        if not ln:
            if out and out[-1] != "":
                out.append("")
            continue

        if ln in drop_exact:
            continue

        if ln.startswith("Searching the web for"):
            continue
        if ln.startswith("Searched the web for"):
            continue

        out.append(ln)

    cleaned: list[str] = []
    for ln in out:
        if ln == "" and (not cleaned or cleaned[-1] == ""):
            continue
        cleaned.append(ln)

    return "\n".join(cleaned).strip()


def is_bad_answer(answer: str, prompt: str) -> bool:
    a = (answer or "").strip()
    p = (prompt or "").strip()

    if not a:
        return True

    if a.lower() == p.lower():
        return True

    if len(a) <= 3 and len(p) > 6:
        return True

    return False


def ha_tts_speak(token: str, message: str) -> None:
    payload = {
        "entity_id": TTS_ENTITY,
        "media_player_entity_id": MEDIA_PLAYER,
        "message": message,
    }

    req = urllib.request.Request(
        f"{HA_URL}/api/services/tts/speak",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            r.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"ERROR: HA tts.speak HTTP {e.code}\n{body}")


def usage() -> None:
    print('Usage: lumo.py "your prompt"')
    print("       lumo.py        (reads prompt from HA input_text.lumo_prompt)")


def main() -> None:
    token = read_token()

    if len(sys.argv) >= 2:
        prompt = " ".join(sys.argv[1:]).strip()
    else:
        prompt = ha_get_state(token, PROMPT_ENTITY)

    if not prompt:
        usage()
        raise SystemExit(2)

    lumo_payload = {"prompt": prompt}

    attempts = [0.0, 0.6, 1.2]
    last_raw = ""
    last_clean = ""

    for delay in attempts:
        if delay:
            time.sleep(delay)

        status, headers, body = http_post_json(LUMO_URL, lumo_payload, timeout=120)
        raw = parse_response(status, headers, body)
        cleaned = clean_lumo_text(raw)

        last_raw, last_clean = raw, cleaned
        candidate = cleaned if cleaned else raw.strip()

        if not is_bad_answer(candidate, prompt):
            answer = candidate
            break
    else:
        best = (last_clean or last_raw).strip()
        if not best:
            raise SystemExit("ERROR: empty response from Lumo")
        answer = best

    if len(answer) > 2500:
        answer = answer[:2500].rstrip() + "…"

    print("\n=== Lumo Answer (spoken) ===")
    print(answer)
    print("============================\n")

    ha_tts_speak(token, answer)
    print("OK: Spoken via Voice Preview.")


if __name__ == "__main__":
    main()
