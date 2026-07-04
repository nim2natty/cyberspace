"""Real Vast.ai API client for TrainABaby.

Vast.ai exposes a REST API at https://console.vast.ai/api/v0 (Bearer auth).
This client implements the instance lifecycle used by training:
  search offers (PUT /asks/)  ->  rent one (PUT /asks/{id}/)  ->
  list (GET /instances/)      ->  destroy (DELETE /instances/{id}/)

Without a VAST_API_KEY the search still runs against the public offers endpoint
so the user can see live prices; only rent/destroy require a key.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import httpx

API_BASE = "https://console.vast.ai/api/v0"


def api_key() -> Optional[str]:
    return os.environ.get("VAST_API_KEY") or os.environ.get("VAST_KEY")


@dataclass
class Offer:
    id: int
    gpu_name: str
    num_gpus: int
    dph_total: float          # $/hr total (gpu + disk + bandwidth)
    dlperf: float             # deep-learning perf score
    disk_space: float         # GB available
    cuda_max_good: str        # cuda version
    reliability: float
    geolocation: str

    def display(self) -> str:
        return (f"#{self.id} {self.gpu_name} x{self.num_gpus}  "
                f"${self.dph_total:.3f}/hr  dlperf={self.dlperf:.0f}  "
                f"disk={self.disk_space:.0f}GB  {self.geolocation}")


class VastClient:
    def __init__(self, key: Optional[str] = None, timeout: float = 20.0):
        self.key = key or api_key()
        self.timeout = timeout

    def _headers(self) -> dict:
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.key:
            h["Authorization"] = f"Bearer {self.key}"
        return h

    def search(self, *, gpu_name: Optional[str] = None, num_gpus: int = 1,
               max_dph: Optional[float] = None, min_disk_gb: float = 50.0,
               limit: int = 12) -> list[Offer]:
        """Search the live Vast.ai offer board. Returns offers cheapest-first."""
        # Build the query filter object in Vast's DSL.
        q: dict = {
            "verified": {"eq": True},
            "external": {"eq": False},
            "rentable": {"eq": True},
            "num_gpus": {"gte": int(num_gpus)},
            "disk_space": {"gte": float(min_disk_gb)},
            "total_flops": {"gte": 0},
        }
        if gpu_name:
            q["gpu_name"] = {"eq": gpu_name}
        if max_dph:
            q["dph_total"] = {"lte": float(max_dph)}
        body = {"query": q, "order": [["dph_total", "asc"]], "limit": int(limit)}
        r = httpx.put(f"{API_BASE}/asks/", headers=self._headers(),
                      json=body, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        offers = []
        for o in data.get("offers", []):
            try:
                offers.append(Offer(
                    id=o["id"],
                    gpu_name=o.get("gpu_name", "?"),
                    num_gpus=int(o.get("num_gpus", 1)),
                    dph_total=float(o.get("dph_total", 0)),
                    dlperf=float(o.get("dlperf", 0)),
                    disk_space=float(o.get("disk_space", 0)),
                    cuda_max_good=str(o.get("cuda_max_good", "")),
                    reliability=float(o.get("reliability2", 0) or 0),
                    geolocation=o.get("geolocation", "?"),
                ))
            except Exception:
                continue
        return offers

    def rent(self, offer_id: int, *, image: str, disk_gb: float = 80.0,
             onstart: str = "") -> dict:
        """Rent an instance from a search offer. Requires VAST_API_KEY."""
        if not self.key:
            raise RuntimeError("renting needs VAST_API_KEY (https://cloud.vast.ai/account/settings/)")
        body = {
            "client_id": "me", "image": image, "disk": float(disk_gb),
            "label": "trainababy", "onstart": onstart,
            "runtype": "ssh", "python_utf8": True, "lang_utf8": True,
            "use_ssh_proxy": False, "force": False,
        }
        r = httpx.put(f"{API_BASE}/asks/{int(offer_id)}/", headers=self._headers(),
                      json=body, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def instances(self) -> list[dict]:
        """List your rented instances. Requires a key."""
        if not self.key:
            return []
        r = httpx.get(f"{API_BASE}/instances/", headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("instances", [])

    def destroy(self, instance_id: int) -> dict:
        if not self.key:
            raise RuntimeError("destroy needs VAST_API_KEY")
        r = httpx.delete(f"{API_BASE}/instances/{int(instance_id)}/",
                         headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()
