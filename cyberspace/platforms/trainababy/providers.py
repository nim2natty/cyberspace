"""GPU-rental marketplaces TrainABaby can drive.

Vast.ai is the primary integration (real REST API at console.vast.ai/api/v0).
RunPod / Lambda / local are supported as provider records so the plan/serve steps
can target them; the live `instances` search is implemented for Vast.ai.
"""
from __future__ import annotations

PROVIDERS = {
    "vastai": {
        "label": "Vast.ai",
        "api_base": "https://console.vast.ai/api/v0",
        "auth": "header Authorization: Bearer $VAST_API_KEY",
        "key_url": "https://cloud.vast.ai/account/settings/",
        "note": "Decentralized spot GPU market. Cheapest $/hr. Best for training.",
        "live": True,
    },
    "runpod": {
        "label": "RunPod",
        "api_base": "https://api.runpod.io/v2",
        "auth": "header Authorization: Bearer $RUNPOD_API_KEY",
        "key_url": "https://www.runpod.io/console/user/settings",
        "note": "Serverless + pod GPUs. Good for both training and serving.",
        "live": False,
    },
    "lambda": {
        "label": "Lambda Labs",
        "api_base": "https://cloud.lambdalabs.com/api/v1",
        "auth": "header Authorization: Bearer $LAMBDA_API_KEY",
        "key_url": "https://cloud.lambdalabs.com/api-keys",
        "note": "Stable H100/A100 clusters. Higher reliability, higher price.",
        "live": False,
    },
    "local": {
        "label": "Local (your own GPU)",
        "api_base": "",
        "auth": "none",
        "key_url": "",
        "note": "Run on this machine if you have a capable GPU (nvidia-smi).",
        "live": False,
    },
}


def provider(key: str) -> dict:
    return PROVIDERS.get(key, PROVIDERS["vastai"])
