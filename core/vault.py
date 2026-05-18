import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


VAULT_PATH = Path(".nexusrecon") / "vault.json"


def list_vault_keys(path: Path = VAULT_PATH) -> List[dict]:
    payload = _load(path)
    keys = []
    for name, item in sorted(payload.get("keys", {}).items()):
        keys.append(
            {
                "name": name,
                "masked": _mask(_decode(item.get("value", ""))),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "source": "vault",
            }
        )
    for name, value in sorted(os.environ.items()):
        if name.endswith("_API_KEY") and name not in payload.get("keys", {}):
            keys.append({"name": name, "masked": _mask(value), "created_at": None, "updated_at": None, "source": "env"})
    return keys


def set_vault_key(name: str, value: str, path: Path = VAULT_PATH) -> dict:
    clean_name = name.strip().upper()
    if not clean_name.endswith("_API_KEY"):
        raise ValueError("Vault key names must end with _API_KEY.")
    if not value.strip():
        raise ValueError("Vault value cannot be empty.")

    payload = _load(path)
    now = datetime.now(timezone.utc).isoformat()
    existing = payload.setdefault("keys", {}).get(clean_name, {})
    payload["keys"][clean_name] = {
        "value": _encode(value.strip()),
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
    }
    _save(payload, path)
    return {"name": clean_name, "masked": _mask(value), "updated_at": now, "source": "vault"}


def delete_vault_key(name: str, path: Path = VAULT_PATH) -> bool:
    payload = _load(path)
    existed = payload.get("keys", {}).pop(name.strip().upper(), None) is not None
    _save(payload, path)
    return existed


def vault_status() -> dict:
    keys = list_vault_keys()
    return {
        "path": str(VAULT_PATH),
        "total_keys": len(keys),
        "keys": keys,
        "supported_names": [
            "WHOXY_API_KEY",
            "PDCP_API_KEY",
            "HIBP_API_KEY",
            "ETHERSCAN_API_KEY",
            "MISTRAL_API_KEY",
            "OPENAI_API_KEY",
        ],
    }


def _load(path: Path) -> Dict[str, dict]:
    if not path.exists():
        return {"keys": {}}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {"keys": {}}
    except (json.JSONDecodeError, OSError):
        return {"keys": {}}


def _save(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _encode(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii")


def _decode(value: str) -> str:
    try:
        return base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")
    except Exception:
        return ""


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}{'*' * (len(value) - 7)}{value[-4:]}"
