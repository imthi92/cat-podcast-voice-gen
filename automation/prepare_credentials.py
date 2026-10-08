#!/usr/bin/env python3
"""Decode + validate YouTube credentials for GitHub Actions.

Environment inputs (the normal, preferred source):
    YT_TOKEN_B64    -> automation/youtube_token.pickle
    YT_CLIENT_B64   -> automation/client_secret.json

Fallback sources (used automatically when a secret is missing, empty or not
usable), so a bad/absent secret degrades instead of breaking every run:
    1. automation/github_token_base64.txt   / automation/github_secret_base64.txt
    2. the same files fetched from the sibling repo (they are public there)

Why this replaced the old workflow step
---------------------------------------
The previous step was:

    echo "${{ secrets.YOUTUBE_TOKEN_BASE64 }}" | base64 -d > automation/youtube_token.pickle

which died with a bare "base64: invalid input" (exit 1) when the secret was not
clean base64, and silently wrote an EMPTY file when the secret was absent - that
then surfaced much later as "Token file corrupted (Ran out of input)" or a
JSONDecodeError, nowhere near the real cause.

This script reports missing secrets, accepts base64 or a raw value, verifies the
result is real OAuth material, and emits ::error::/::warning:: annotations with
the exact command needed to fix it. Secret values are never printed.
"""

import base64
import json
import os
import pickle
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN_OUT = os.path.join(HERE, "youtube_token.pickle")
SECRET_OUT = os.path.join(HERE, "client_secret.json")

TOKEN_ENV = "YT_TOKEN_B64"
CLIENT_ENV = "YT_CLIENT_B64"

TOKEN_FILE = "github_token_base64.txt"
CLIENT_FILE = "github_secret_base64.txt"

# Public raw URLs of the credential files (used only as a last resort).
BRIDGE_URL = ("https://raw.githubusercontent.com/imthi92/cat-podcast-voice-gen"
              "/master/automation/{name}")

errors = []
warnings = []


def _b64decode(value):
    """Return decoded bytes, or None when the value is not clean base64."""
    candidate = re.sub(r"\s+", "", value)
    if len(candidate) < 4 or len(candidate) % 4 != 0:
        return None
    try:
        return base64.b64decode(candidate, validate=True)
    except Exception:
        return None


def _write(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(data)
    return len(data)


def _read_local(name):
    path = os.path.join(HERE, name)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def _read_bridge(name):
    """Fetch a credential file from the sibling public repo (last resort)."""
    try:
        with urllib.request.urlopen(BRIDGE_URL.format(name=name), timeout=15) as resp:
            return resp.read().decode("utf-8", "replace").strip()
    except Exception as exc:
        warnings.append("Could not fetch fallback %s: %s" % (name, exc))
        return None


def _validate(path, data, validator):
    _write(path, data)
    return validator(path, data)


def resolve(label, env_name, fallback_file, out_path, validator):
    """Pick the first source that yields valid credentials.

    Returns True on success. Sources are tried in order: repo secret -> locally
    committed file -> the same file fetched from the sibling public repo.
    """
    sources = []

    env_value = os.environ.get(env_name, "").strip()
    if env_value:
        sources.append(("%s GitHub secret" % label, env_value))
    else:
        warnings.append("%s GitHub secret is missing/empty - trying fallbacks"
                        % label)

    local = _read_local(fallback_file)
    if local:
        sources.append(("committed file %s" % fallback_file, local))
    else:
        bridge = _read_bridge(fallback_file)
        if bridge:
            sources.append(("public sibling-repo file %s" % fallback_file, bridge))

    for origin, value in sources:
        for interpretation, data in (("base64", _b64decode(value)),
                                     ("raw", value.encode("utf-8"))):
            if not data:
                continue
            problem = _validate(out_path, data, validator)
            if problem is None:
                print("%s: OK via %s [%s, %d bytes] -> %s"
                      % (label, origin, interpretation, len(data),
                         os.path.basename(out_path)))
                if "GitHub secret" not in origin:
                    warnings.append(
                        "%s came from %s instead of its GitHub secret. Set the "
                        "secret to stop depending on committed credentials."
                        % (label, origin))
                return True
            if interpretation == "base64":
                print("%s: %s decoded (%d bytes) but did not validate (%s) - "
                      "retrying as a raw value"
                      % (label, origin, len(data), problem))

    if not os.path.exists(out_path):
        _write(out_path, b"")
    errors.append(
        "%s is unusable and no fallback worked. Fix: on a machine with working "
        "credentials run  python setup_github_secrets.py  then paste the value "
        "it prints into Settings -> Secrets and variables -> Actions."
        % label
    )
    return False


def validate_client_secret(path, data):
    """Return None when client_secret.json is a usable OAuth client file."""
    try:
        cfg = json.loads(data.decode("utf-8"))
    except Exception as exc:
        return "not valid JSON: %s" % exc
    if not isinstance(cfg, dict):
        return "expected a JSON object"
    scope = cfg.get("installed") or cfg.get("web") or {}
    if not isinstance(scope, dict):
        return "missing 'installed'/'web' block"
    missing = [k for k in ("client_id", "client_secret") if not scope.get(k)]
    if missing:
        return "missing %s" % ", ".join(missing)
    print("client_secret: OK (OAuth client %s...)" % scope["client_id"][:8])
    return None


def validate_token(path, data):
    """Return None when youtube_token.pickle holds usable OAuth credentials.

    authenticate_youtube.py always pickle.dumps a Credentials object (or a
    dict), so anything that is not a pickle is rejected here -- including a
    bare refresh token, which no loader in this repo can read.
    """
    if data[:1] != b"\x80" and data[:1] != b"(":
        return ("not a pickle (starts with 0x%02x) - re-create it with: "
                "python setup_github_secrets.py" % (data[:1][0] if data else 0))

    try:
        obj = pickle.loads(data)
    except ModuleNotFoundError as exc:
        if data[:1] == b"\x80":
            print("token: pickle header OK (cannot fully verify: %s)" % exc)
            return None
        return "not a pickle: %s" % exc
    except Exception as exc:
        return "not a pickle (%s: %s)" % (type(exc).__name__, exc)

    if hasattr(obj, "refresh_token"):
        if not obj.refresh_token:
            return "Credentials object has no refresh_token (re-run authenticate_youtube.py)"
        print("token: OK (google Credentials object, refresh_token present)")
        return None
    if isinstance(obj, dict):
        if not obj.get("refresh_token"):
            return "token dict has no refresh_token"
        print("token: OK (dict, %d keys, refresh_token present)" % len(obj))
        return None
    return "unexpected object type %s" % type(obj).__name__


def probe_refresh(path):
    """Fail fast when the OAuth refresh token itself is dead.

    Without this, a revoked token burns 10 minutes generating a video and only
    surfaces at upload time (and, before the exit-code fix, reported success
    while publishing nothing). Refreshing here also persists a fresh access
    token so the upload does not have to refresh again.
    """
    try:
        import pickle
        from google.auth.transport.requests import Request
    except Exception as exc:
        print("token: refresh probe skipped (%s)" % exc)
        return None

    try:
        with open(path, "rb") as fh:
            obj = pickle.load(fh)
    except Exception as exc:
        return "token could not be read for the refresh probe: %s" % exc

    if not hasattr(obj, "refresh"):
        return None  # plain/dict payload - the loader decides what to do

    try:
        if getattr(obj, "expired", True) or not getattr(obj, "token", None):
            obj.refresh(Request())
        with open(path, "wb") as fh:
            pickle.dump(obj, fh)
        print("token: refresh OK (access token valid until %s)"
              % getattr(obj, "expiry", "unknown"))
        return None
    except Exception as exc:
        msg = str(exc)
        if "invalid_grant" in msg:
            return ("the YouTube refresh token was revoked or expired (%s). "
                    "Fix on a machine with a browser: "
                    "python automation/authenticate_youtube.py, then update the "
                    "YOUTUBE_TOKEN_BASE64 secret (or the committed "
                    "automation/github_token_base64.txt fallback file)."
                    % msg[:180])
        print("token: refresh probe hit a transient error (%s) - continuing"
              % msg[:180])
        return None


def main():
    print("=" * 60)
    print("YOUTUBE CREDENTIALS - resolve, decode, validate")
    print("=" * 60)

    ok_token = resolve("YOUTUBE_TOKEN_BASE64", TOKEN_ENV, TOKEN_FILE,
                       TOKEN_OUT, validate_token)
    ok_client = resolve("YOUTUBE_CLIENT_SECRET_BASE64", CLIENT_ENV, CLIENT_FILE,
                        SECRET_OUT, validate_client_secret)

    if ok_token:
        probe_problem = probe_refresh(TOKEN_OUT)
        if probe_problem:
            ok_token = False
            errors.append("YOUTUBE_TOKEN_BASE64: " + probe_problem)

    for w in dict.fromkeys(warnings):
        print("::warning title=YouTube credentials::%s" % w)

    if not (ok_token and ok_client):
        for err in dict.fromkeys(errors):
            print("::error title=YouTube credentials::%s" % err)
        print("=" * 60)
        print("FAILED - YouTube credentials could not be resolved.")
        return 1

    print("All YouTube credentials resolved and validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
