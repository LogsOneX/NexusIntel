# Investigator Brain

NexusIntel Investigator Brain adalah lapisan reasoning lokal yang **deterministic-first** dan **LLM-assisted second**. Fakta diputuskan oleh validasi evidence, confidence, noise, dan provenance. Model lokal hanya membantu meringkas, menjelaskan, dan merencanakan langkah berikutnya.

## Prinsip

- Tidak ada synthetic intelligence yang dimasukkan ke graph.
- AI tidak boleh menaikkan status finding tanpa evidence.
- Setiap judgment harus mengutip evidence ID, source URL, raw hash, atau menyatakan `insufficient evidence`.
- Attribution ke orang nyata hanya boleh kuat jika ada bukti publik langsung, independen, dan confidence rule terpenuhi.

## Modul

- `evidence_reasoner.py`: memetakan node/edge ke evidence dan menghitung reliability/directness/freshness/corroboration.
- `noise_killer.py`: menekan login page, auth wall, soft 404, CDN-only, registrar privacy, dan candidate URL noise.
- `validator.py`: memberi label `VERIFIED`, `STRONG`, `PROBABLE`, `WEAK`, `CANDIDATE`, `NOISE`, atau `INSUFFICIENT_EVIDENCE`.
- `hypothesis.py`: membuat hypothesis berbasis shared artifacts tanpa otomatis mengklaim identitas.
- `planner.py`: memberi next best actions yang tetap pasif/legal.
- `local_llm.py`: adapter rules/Ollama/llama.cpp/OpenAI-compatible.
- `memory.py`: menyimpan compact case memory di `investigation.meta.ai_memory`.
- `report.py`: menghitung readiness score untuk export.

## Endpoint Utama

- `POST /api/v1/oracle/chat`
- `GET /api/v1/investigations/{id}/validation`
- `POST /api/v1/investigations/{id}/planner/next-actions`
- `POST /api/v1/investigations/{id}/hypotheses/generate`
- `GET /api/v1/investigations/{id}/report-readiness`
