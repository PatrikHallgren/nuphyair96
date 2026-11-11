"""Home Assistant light payloads.

The token is sent as a Bearer header and is never placed in the JSON body.
Callers pass the token in; this module does not read the environment itself
except through ``resolve_token``.
"""

import json
import re
from pathlib import Path
from urllib import error, request

from air96_protocol import hex_to_rgb

ENTITY = re.compile(r"light\.[A-Za-z0-9_]+")
URL = re.compile(r"https?://[^/\s]+(?:/[^\s]*)?$")
MIN_TOKEN_LENGTH = 8
# Bracketed-paste markers a terminal inserts around a paste. `read -rsp` keeps them.
_PASTE_MARKERS = ("\x1b[200~", "\x1b[201~")


class HomeAssistantError(RuntimeError):
    pass


def normalize_url(url):
    if not isinstance(url, str) or not URL.fullmatch(url.strip()):
        raise HomeAssistantError("Home Assistant URL must start with http:// or https://")
    return url.strip().rstrip("/")


def normalize_entities(entities):
    if isinstance(entities, str):
        entities = [part.strip() for part in entities.split(",") if part.strip()]
    if not isinstance(entities, list) or not entities:
        raise HomeAssistantError("Add at least one light.entity id")
    cleaned = []
    for entity in entities:
        if not isinstance(entity, str) or not ENTITY.fullmatch(entity.strip()):
            raise HomeAssistantError(f"Not a light entity id: {entity}")
        cleaned.append(entity.strip())
    return cleaned


def turn_on_payload(entities, color, brightness):
    red, green, blue = hex_to_rgb(color)
    if type(brightness) is not int or not 0 <= brightness <= 255:
        raise HomeAssistantError("Brightness must be 0-255")
    return {
        "entity_id": normalize_entities(entities),
        "rgb_color": [red, green, blue],
        "brightness": brightness,
    }


def sanitize_token(raw):
    """Drop bracketed-paste markers and surrounding whitespace. Never logs the value."""
    if not isinstance(raw, str):
        return ""
    text = raw
    for marker in _PASTE_MARKERS:
        text = text.replace(marker, "")
    return text.strip()


def check_token(token):
    """Accept a sanitized token. The message names the problem and not the value."""
    if not isinstance(token, str) or token == "":
        raise HomeAssistantError("Home Assistant token is missing")
    problems = []
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in token):
        problems.append("it contains whitespace or control characters")
    if len(token) < MIN_TOKEN_LENGTH:
        problems.append("it is too short")
    if problems:
        raise HomeAssistantError("Home Assistant token is malformed: " + " and ".join(problems))
    return token


def prepare_token(raw):
    if not isinstance(raw, str) or raw.strip() == "":
        raise HomeAssistantError("Home Assistant token is missing")
    cleaned = sanitize_token(raw)
    if cleaned == "":
        raise HomeAssistantError(
            "Home Assistant token is malformed: it contains whitespace or control characters"
        )
    return check_token(cleaned)


def service_request(url, token, payload):
    token = prepare_token(token)
    if not isinstance(payload, dict) or "entity_id" not in payload or "rgb_color" not in payload:
        raise HomeAssistantError("Incomplete light payload")
    return {
        "url": normalize_url(url) + "/api/services/light/turn_on",
        "method": "POST",
        "headers": {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        "body": json.dumps(payload).encode("utf-8"),
    }


def resolve_token(environ, token_env, token_file, inline=""):
    if inline:
        return prepare_token(inline)
    name = token_env or "HA_TOKEN"
    if environ.get(name):
        return prepare_token(environ[name])
    if token_file:
        try:
            raw = Path(token_file).read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise HomeAssistantError("Home Assistant token is malformed: it is not text") from exc
        except OSError as exc:
            raise HomeAssistantError(
                f"Home Assistant token file is unreadable: {exc.strerror or 'unknown error'}"
            ) from exc
        return prepare_token(raw)
    raise HomeAssistantError("Home Assistant token is missing")


def send(prepared, opener=None, timeout=5):
    call = opener or request.urlopen
    req = request.Request(prepared["url"], data=prepared["body"], headers=prepared["headers"], method="POST")
    try:
        with call(req, timeout=timeout) as response:
            status = getattr(response, "status", None) or response.getcode()
            raw = response.read(4096)
    except error.HTTPError as exc:
        detail = exc.read(300).decode("utf-8", errors="replace") if exc.fp else ""
        raise HomeAssistantError(f"Home Assistant returned HTTP {exc.code} {detail[:180]}".strip()) from exc
    except error.URLError as exc:
        raise HomeAssistantError(f"Home Assistant unreachable: {exc.reason}") from exc
    except OSError as exc:
        raise HomeAssistantError(f"Home Assistant unreachable: {exc.strerror or exc}") from exc
    if status and int(status) >= 300:
        raise HomeAssistantError(f"Home Assistant returned HTTP {status}")
    return {"status": int(status or 200), "body": raw.decode("utf-8", errors="replace")[:400]}
