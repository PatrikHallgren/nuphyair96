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


def service_request(url, token, payload):
    if not isinstance(token, str) or len(token) < 8 or any(ch.isspace() for ch in token):
        raise HomeAssistantError("Home Assistant token is missing")
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
        return inline
    name = token_env or "HA_TOKEN"
    if environ.get(name):
        return environ[name]
    if token_file:
        try:
            return Path(token_file).read_text().strip()
        except OSError as exc:
            raise HomeAssistantError(f"Cannot read token file: {exc.strerror or exc}") from exc
    return ""


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
