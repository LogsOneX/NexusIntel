from __future__ import annotations

NETWORK_IO_QUEUE = "network_io"
ML_GPU_QUEUE = "ml_gpu"
DEFAULT_QUEUE = "default"

TASK_ROUTES = {
    "nexusintel.nexusrecon": {"queue": NETWORK_IO_QUEUE},
    "nexusintel.email_google": {"queue": NETWORK_IO_QUEUE},
    "nexusintel.domain": {"queue": NETWORK_IO_QUEUE},
    "nexusintel.phone": {"queue": NETWORK_IO_QUEUE},
    "nexusintel.full_identity_pipeline": {"queue": NETWORK_IO_QUEUE},
    "nexusintel.serverless_invoke": {"queue": NETWORK_IO_QUEUE},
    "nexusintel.crypto_wallet": {"queue": NETWORK_IO_QUEUE},
    "nexusintel.google_footprint": {"queue": NETWORK_IO_QUEUE},
    "nexusintel.watchlist_tick": {"queue": NETWORK_IO_QUEUE},
    "nexusintel.watchlist_sweep_all": {"queue": NETWORK_IO_QUEUE},
    "nexusintel.entity_resolution": {"queue": ML_GPU_QUEUE},
}
