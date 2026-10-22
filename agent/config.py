"""Load settings and sources from config/, with environment overrides."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    settings: dict[str, Any]
    sources: list[dict[str, Any]]
    tracked_labs: list[str]
    lab_domains: dict[str, str]
    data_dir: Path
    review_mode: bool
    extra: dict[str, Any] = field(default_factory=dict)

    def canon_lab(self, name: str | None) -> str:
        """One spelling per lab: apply aliases, and match tracked labs case-insensitively."""
        n = (name or "").strip()
        if not n:
            return ""
        aliases = {k.lower(): v for k, v in (self.extra.get("lab_aliases") or {}).items()}
        if n.lower() in aliases:
            return aliases[n.lower()]
        return next((t for t in self.tracked_labs if t.lower() == n.lower()), n)

    @property
    def providers(self) -> list[dict[str, Any]]:
        return self.settings["providers"]

    @property
    def run(self) -> dict[str, Any]:
        return self.settings["run"]

    @property
    def guardrails(self) -> dict[str, Any]:
        return self.settings["guardrails"]

    @property
    def limits(self) -> dict[str, Any]:
        return self.settings["limits"]

    @property
    def gdelt(self) -> dict[str, Any]:
        return self.settings.get("gdelt", {})


def load_config(config_dir: Path | None = None, data_dir: Path | None = None) -> Config:
    config_dir = config_dir or ROOT / "config"
    settings = yaml.safe_load((config_dir / "settings.yaml").read_text())
    src = yaml.safe_load((config_dir / "sources.yaml").read_text())

    # Environment overrides (repository variables in GitHub Actions)
    for env, key, cast in (
        ("MAX_REQUESTS_PER_RUN", "max_requests_per_run", int),
        ("MAX_REQUESTS_PER_DAY", "max_requests_per_day", int),
        ("MAX_TOKENS_PER_DAY", "max_tokens_per_day", int),
    ):
        if os.environ.get(env):
            settings["limits"][key] = cast(os.environ[env])
    if os.environ.get("MAX_STORIES_PER_RUN"):
        settings["run"]["max_stories_per_run"] = int(os.environ["MAX_STORIES_PER_RUN"])

    return Config(
        settings=settings,
        sources=src.get("sources", []),
        tracked_labs=src.get("tracked_labs", []),
        lab_domains=src.get("lab_domains", {}),
        data_dir=Path(data_dir or os.environ.get("DATA_DIR") or ROOT / "data"),
        review_mode=_env_bool("REVIEW_MODE", settings.get("review_mode", True)),
        extra={"lab_aliases": src.get("lab_aliases", {}), "video_channels": src.get("video_channels", [])},
    )
