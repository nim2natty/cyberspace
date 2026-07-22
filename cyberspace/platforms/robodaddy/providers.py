"""GPU-rental marketplace records for RoboDaddy.

Vast.ai is the implemented live integration. Other providers are listed as
planning metadata until lifecycle clients are added.
"""
from __future__ import annotations

PROVIDERS = {
    "vastai": {
        "label": "Vast.ai",
        "api_base": "https://console.vast.ai/api/v0",
        "auth": "header Authorization: Bearer $VAST_API_KEY",
        "key_url": "https://cloud.vast.ai/account/settings/",
        "note": "Decentralized spot GPU market with variable hourly offers.",
        "live": True,
    },
    "runpod": {
        "label": "RunPod",
        "api_base": "https://api.runpod.io/v2",
        "auth": "header Authorization: Bearer $RUNPOD_API_KEY",
        "key_url": "https://www.runpod.io/console/user/settings",
        "note": "Provider metadata only; lifecycle automation is not implemented.",
        "live": False,
    },
    "lambda": {
        "label": "Lambda Labs",
        "api_base": "https://cloud.lambdalabs.com/api/v1",
        "auth": "header Authorization: Bearer $LAMBDA_API_KEY",
        "key_url": "https://cloud.lambdalabs.com/api-keys",
        "note": "Provider metadata only; lifecycle automation is not implemented.",
        "live": False,
    },
    "local": {
        "label": "Local (your own GPU)",
        "api_base": "",
        "auth": "none",
        "key_url": "",
        "note": "Provider metadata only; generated job files can be run manually.",
        "live": False,
    },
}


def provider(key: str) -> dict:
    return PROVIDERS.get(key, PROVIDERS["vastai"])
