#!/usr/bin/env python3
"""TONE3000 API helper (device sign-in, IR search, download).
  t3k.py login                  device flow: prints a code to enter at tone3000.com/activate, stores tokens
  t3k.py search "<query>" [n]   IR tones matching the query (format=ir)
  t3k.py get <tone_id> <dir>    download all models (IR WAVs) of a tone
Tokens: ~/.config/t3k/tokens.json (not in the repo)."""
import json, os, sys, time, urllib.request, urllib.parse
API = "https://www.tone3000.com/api/v1"; CID = "t3k_pub_-1C7RcJxtAyQPiqqckP5WUr3YpEB2xFX"
TOK = os.path.expanduser("~/.config/t3k/tokens.json")


def post(path, data):
    req = urllib.request.Request(API + path, urllib.parse.urlencode(data).encode(), {"Content-Type": "application/x-www-form-urlencoded"})
    try: return json.load(urllib.request.urlopen(req, timeout=30)), 200
    except urllib.error.HTTPError as e: return json.loads(e.read() or b"{}"), e.code


def save(t):
    os.makedirs(os.path.dirname(TOK), exist_ok=True); t["expires_at"] = time.time() + t.get("expires_in", 3600) - 60
    json.dump(t, open(TOK, "w")); os.chmod(TOK, 0o600)


def token():
    t = json.load(open(TOK))
    if time.time() > t["expires_at"]:
        r, c = post("/oauth/token", dict(grant_type="refresh_token", refresh_token=t["refresh_token"], client_id=CID))
        if c != 200: sys.exit("token refresh failed; run t3k.py login")
        save(r); t = r
    return t["access_token"]


def get(path, raw=False):
    req = urllib.request.Request(path if path.startswith("http") else API + path, headers={"Authorization": "Bearer " + token(), "User-Agent": "pm-cfw-ir-tool/1.0 (+personal pedal project)"})
    r = urllib.request.urlopen(req, timeout=60); return r.read() if raw else json.load(r)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "login":
        r, c = post("/oauth/device_authorization", dict(client_id=CID))
        if c != 200: sys.exit(f"device authorization failed: {r}")
        print(f"CODE {r['user_code']}  ->  {r['verification_uri']}", flush=True); wait = r.get("interval", 5); end = time.time() + r["expires_in"]
        while time.time() < end:
            time.sleep(wait)
            t, c = post("/oauth/token", dict(grant_type="urn:ietf:params:oauth:grant-type:device_code", device_code=r["device_code"], client_id=CID))
            if c == 200: save(t); print("signed in", flush=True); break
            if t.get("error") == "slow_down": wait += 5
            elif t.get("error") != "authorization_pending": sys.exit(f"sign-in failed: {t}")
    elif a[0] == "search":
        q = urllib.parse.urlencode(dict(query=a[1], format=os.environ.get("T3K_FORMAT", "ir"), page_size=int(a[2]) if len(a) > 2 else 10, sort=os.environ.get("T3K_SORT", "best-match"), **({"gears": os.environ["T3K_GEAR"]} if os.environ.get("T3K_GEAR") else {})))
        for t in get("/tones/search?" + q).get("data", []):
            print(t["id"], "|", t.get("title"), "|", (t.get("user") or {}).get("username"), "| dl", t.get("downloads_count"), "| models", t.get("models_count"), "| license", t.get("license"))
    elif a[0] == "get":
        os.makedirs(a[2], exist_ok=True); ms = get(f"/models?tone_id={a[1]}&page_size=100").get("data", [])[:int(os.environ.get("T3K_MAX", "1000"))]
        for m in ms:
            fn = os.path.join(a[2], f"{a[1]}_{m['id']}_" + "".join(ch if ch.isalnum() or ch in "-._" else "_" for ch in m.get("name", "ir"))[:60])
            if not fn.lower().endswith(".wav"): fn += ".wav"
            open(fn, "wb").write(get(m["model_url"], raw=True))
        print(f"tone {a[1]}: {len(ms)} files -> {a[2]}")
