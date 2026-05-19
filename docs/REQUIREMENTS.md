# System Requirements

Dokumen ini menjelaskan kebutuhan hardware, storage, dan runtime untuk menjalankan NexusIntel.

Repository resmi:

```text
https://github.com/LogsOneX/NexusIntel
```

## Minimum

Cocok untuk testing ringan, single user, dan beberapa investigation kecil.

| Resource | Minimum |
| --- | --- |
| CPU | 2 core / 2 vCPU |
| RAM | 4 GB |
| Storage kosong | 12 GB |
| OS | Linux x86_64 direkomendasikan |
| Runtime | Docker Engine 24+ dan Docker Compose v2 |

## Recommended

Cocok untuk pemakaian harian yang lebih nyaman.

| Resource | Recommended |
| --- | --- |
| CPU | 4 core / 4 vCPU |
| RAM | 8 GB |
| Storage kosong | 25 GB |
| Network | Koneksi stabil untuk DNS/HTTP public-source recon |

## Heavy Use

Cocok untuk banyak case, graph besar, dan worker yang lebih agresif.

| Resource | Heavy |
| --- | --- |
| CPU | 4-8 core |
| RAM | 16 GB |
| Storage kosong | 50 GB+ |
| Worker concurrency | 2-4, naikkan bertahap |

## Estimasi Storage

| Komponen | Estimasi |
| --- | --- |
| Docker images | 2-5 GB |
| Docker build cache | 2-10 GB, tergantung frekuensi build |
| `data/postgres` | Mulai kecil, bisa 1-20 GB+ tergantung jumlah investigation |
| `data/redis` | Biasanya ratusan MB, tergantung task/log history |
| CLI output `results/`, `reports/`, `.nexusrecon/` | Tergantung export yang dibuat |

Untuk fresh install yang nyaman, siapkan minimal 25 GB kosong. Untuk operasi panjang, siapkan 50 GB+.

## Port

Default port:

```text
127.0.0.1:8080
```

Port internal container:

| Service | Port |
| --- | --- |
| frontend | 80 |
| api | 8000 |
| postgres | 5432 internal |
| redis | 6379 internal |

## Dependency Lokal

Untuk deployment utama:

- Docker Engine
- Docker Compose v2
- Git

Untuk development/manual mode:

- Python 3.10+
- Node.js 22+ bila menjalankan frontend di host
- npm

## Disk Maintenance

Cek penggunaan Docker:

```bash
docker system df
```

Bersihkan build cache yang tidak dipakai:

```bash
docker builder prune
```

Matikan stack tanpa menghapus investigation:

```bash
docker compose down
```

Reset semua data investigation lokal:

```bash
docker compose down
sudo rm -rf data
```

Gunakan reset hanya kalau data lama memang sudah tidak diperlukan.
