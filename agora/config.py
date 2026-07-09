"""Config loading. Single YAML file, validated once at startup."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from agora.models import Role, WarrantBand


class RosterEntry(BaseModel):
    role: Role
    tier: str  # key into models map


class MetaTiers(BaseModel):
    frame_tier: str
    judge_tier: str
    synthesizer_tier: str


class Budget(BaseModel):
    max_total_tokens: int
    max_rounds: int
    max_output_tokens_per_call: int


class Thresholds(BaseModel):
    min_mean_warrant: WarrantBand


class Paths(BaseModel):
    prompts_dir: str
    runs_dir: str


class AgoraConfig(BaseModel):
    models: dict[str, str]  # tier name -> model id
    roster: list[RosterEntry]
    meta: MetaTiers
    budget: Budget
    thresholds: Thresholds
    paths: Paths

    def model_for(self, tier: str) -> str:
        return self.models[tier]


def load_config(path: str | Path = "config.yaml") -> AgoraConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return AgoraConfig.model_validate(raw)
