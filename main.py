```python
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

app = FastAPI(title="Effective Config API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def coerce(key, value):
    if key in {"port", "workers"}:
        return int(value)
    if key == "debug":
        return to_bool(value)
    return str(value)


def normalize_layer(layer):
    result = {}
    for key, value in layer.items():
        if value is None:
            continue
        key = str(key).strip()
        if key == "NUM_WORKERS":
            key = "workers"
        elif key.startswith("APP_"):
            key = key[4:].lower()
        else:
            key = key.lower()
        result[key] = value
    return result


@app.get("/effective-config")
async def effective_config(
    request: Request,
    set: list[str] = Query(default=[]),
):
    config = dict(DEFAULTS)

    # Layer 2: environment-specific YAML.
    environment = os.environ.get("APP_ENV", "development")
    yaml_path = BASE_DIR / f"config.{environment}.yaml"
    if yaml_path.exists():
        with yaml_path.open("r", encoding="utf-8") as file:
            yaml_layer = yaml.safe_load(file) or {}
        config.update(normalize_layer(yaml_layer))

    # Layer 3: .env file. Parse it separately so OS variables
    # can take precedence over it.
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        file_layer = dotenv_values(env_path)
        config.update(normalize_layer(file_layer))

    # Layer 4: actual OS environment variables with APP_ prefix.
    os_layer = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("APP_") and key != "APP_ENV"
    }
    config.update(normalize_layer(os_layer))

    # Layer 5: repeated query parameters, e.g. ?set=port=9000&set=debug=true
    for override in request.query_params.getlist("set"):
        if "=" not in override:
            continue
        key, value = override.split("=", 1)
        key = key.strip().lower()
        if key:
            config[key] = value

    # Apply the required types after all layers have been merged.
    result = {key: coerce(key, value) for key, value in config.items()}

    # Never reveal the actual secret.
    if "api_key" in result:
        result["api_key"] = "****"

    return result
```
