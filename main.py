import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Request
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


@app.get("/")
@app.get("/effective-config")
async def effective_config(request: Request):
    config = dict(DEFAULTS)

    # Layer 2: environment-specific YAML
    environment = os.environ.get("APP_ENV", "development")
    yaml_path = BASE_DIR / f"config.{environment}.yaml"

    if yaml_path.exists():
        with yaml_path.open("r", encoding="utf-8") as file:
            yaml_config = yaml.safe_load(file) or {}
        config.update(normalize_layer(yaml_config))

    # Layer 3: .env file
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        config.update(normalize_layer(dotenv_values(env_path)))

    # Layer 4: OS-level APP_* environment variables
    os_config = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("APP_") and key != "APP_ENV"
    }
    config.update(normalize_layer(os_config))

    # Layer 5: repeated CLI-style query overrides
    for override in request.query_params.getlist("set"):
        if "=" not in override:
            continue

        key, value = override.split("=", 1)
        key = key.strip().lower()

        if key:
            if key == "num_workers":
                key = "workers"
            config[key] = value

    result = {key: coerce(key, value) for key, value in config.items()}
    result["api_key"] = "****"

    return result
