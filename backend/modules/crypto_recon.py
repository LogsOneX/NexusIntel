from __future__ import annotations

import os
from typing import Any

import httpx


def classify_wallet(address: str) -> str:
    clean = address.strip()
    if clean.startswith("0x") and len(clean) == 42:
        return "ethereum"
    if 26 <= len(clean) <= 64:
        return "bitcoin"
    return "unknown"


async def lookup_wallet(address: str) -> dict[str, Any]:
    chain = classify_wallet(address)
    if os.getenv("NEXUS_ENV") == "development":
        return {
            "dry_run": True,
            "address": address,
            "chain": chain,
            "balance": "0.00000000",
            "transactions": [
                {"hash": "dry-run-tx-1", "direction": "in", "amount": "0.01000000", "timestamp": "development"},
                {"hash": "dry-run-tx-2", "direction": "out", "amount": "0.00250000", "timestamp": "development"},
            ],
        }
    if chain == "bitcoin":
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"https://blockstream.info/api/address/{address}")
            response.raise_for_status()
            data = response.json()
            tx_response = await client.get(f"https://blockstream.info/api/address/{address}/txs")
            tx_response.raise_for_status()
            txs = tx_response.json()[:10]
        funded = data.get("chain_stats", {}).get("funded_txo_sum", 0)
        spent = data.get("chain_stats", {}).get("spent_txo_sum", 0)
        return {"address": address, "chain": chain, "balance_sats": funded - spent, "transactions": txs}
    return {"address": address, "chain": chain, "error": "No free explorer configured for this chain", "transactions": []}
