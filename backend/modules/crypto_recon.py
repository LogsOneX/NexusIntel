from __future__ import annotations

import os
from typing import Any

import httpx

from backend.modules.evidence_quality import with_quality


def classify_wallet(address: str) -> str:
    clean = address.strip()
    if clean.startswith("0x") and len(clean) == 42:
        return "ethereum"
    if 26 <= len(clean) <= 64:
        return "bitcoin"
    return "unknown"


async def _lookup_bitcoin(address: str) -> dict[str, Any]:
    base = os.getenv("NEXUS_BITCOIN_EXPLORER", "https://blockstream.info/api").rstrip("/")
    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "NexusIntel/2.3 public-osint read-only"}) as client:
        response = await client.get(f"{base}/address/{address}")
        response.raise_for_status()
        data = response.json()
        tx_response = await client.get(f"{base}/address/{address}/txs")
        tx_response.raise_for_status()
        txs = tx_response.json()[:10]
    funded = int(data.get("chain_stats", {}).get("funded_txo_sum", 0))
    spent = int(data.get("chain_stats", {}).get("spent_txo_sum", 0))
    return with_quality({
        "verified": True,
        "status": "verified_public_explorer",
        "address": address,
        "chain": "bitcoin",
        "source": "blockstream_public_explorer",
        "source_url": f"{base}/address/{address}",
        "balance_sats": funded - spent,
        "transactions": txs,
    })


async def _lookup_ethereum(address: str) -> dict[str, Any]:
    rpc_url = os.getenv("NEXUS_ETH_RPC_URL", "https://cloudflare-eth.com").strip()
    payload = {"jsonrpc": "2.0", "method": "eth_getBalance", "params": [address, "latest"], "id": 1}
    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "NexusIntel/2.3 public-osint read-only"}) as client:
        response = await client.post(rpc_url, json=payload)
        response.raise_for_status()
        data = response.json()
    if data.get("error"):
        return with_quality({
            "verified": False,
            "status": "source_rejected_request",
            "address": address,
            "chain": "ethereum",
            "source": "public_ethereum_rpc",
            "source_url": rpc_url,
            "reason": data.get("error"),
            "transactions": [],
        })
    balance_hex = str(data.get("result") or "0x0")
    return with_quality({
        "verified": True,
        "status": "verified_public_rpc",
        "address": address,
        "chain": "ethereum",
        "source": "public_ethereum_rpc",
        "source_url": rpc_url,
        "balance_wei": int(balance_hex, 16),
        "transactions": [],
    })


async def lookup_wallet(address: str) -> dict[str, Any]:
    clean = address.strip()
    chain = classify_wallet(clean)
    if chain == "unknown":
        return with_quality({
            "verified": False,
            "status": "invalid_or_unsupported_wallet",
            "address": clean,
            "chain": chain,
            "reason": "Address format is not recognized as Bitcoin or Ethereum.",
            "transactions": [],
        })
    try:
        if chain == "bitcoin":
            return await _lookup_bitcoin(clean)
        if chain == "ethereum":
            return await _lookup_ethereum(clean)
    except httpx.HTTPError as exc:
        return with_quality({
            "verified": False,
            "status": "source_unavailable",
            "address": clean,
            "chain": chain,
            "reason": str(exc),
            "transactions": [],
        })
    return with_quality({"verified": False, "status": "unsupported_chain", "address": clean, "chain": chain, "transactions": []})
