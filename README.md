# DATA AGGREGATOR / NEXUSRECON UNIFIED OSINT

Sebuah toolkit OSINT terintegrasi untuk:
- Analisis target publik (`aggregate`)
- Enumerasi username lintas platform (`username`)
- Verifikasi email dan temuan metadata (`email`)
- Pemeriksaan nomor telepon ringan (`phone`)
- Intelijen domain RDAP/DNS (`domain`)

## Struktur Folder

- `main.py` - CLI utama yang menggabungkan semua mode.
- `core/` - Engine modul dan generator laporan untuk agregator.
- `modules/` - Plugin analisis modular yang dapat diperluas.
- `recon/` - Scanner username dan NexusRecon Ultimate baru.
- `results/` - Output laporan otomatis.
- `legacy/` - Arsip versi lama `nexusrecon` dan `nexusrecon_ultimate`.

## Instalasi

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Panduan Penggunaan

Jalankan CLI utama:

```bash
python main.py <perintah> [opsi]
```

### Mode `aggregate`
Menjalankan semua modul analisis terhadap target.

```bash
python main.py aggregate -t example.com --save --format json
```

### Mode `username`
Melakukan enumerasi username terhadap banyak platform.

```bash
python main.py username john_doe --workers 50 --timeout 12 --save --format txt
```

### Mode `email`
Memeriksa format email dan metadata publik.

```bash
python main.py email alice@example.com --save --format json
```

### Mode `phone`
Analisis cepat pola nomor telepon.

```bash
python main.py phone "+62 812-3456-7890" --save --format txt
```

### Mode `domain`
Mengambil data RDAP dan DNS untuk domain.

```bash
python main.py domain example.com --save --format json
```

### Menampilkan modul yang tersedia

```bash
python main.py list-modules
```

## Pengembangan Modul

Tambahkan file Python baru ke folder `modules/` dengan fungsi async bernama `run(target: str) -> dict`.
Contoh minimal:

```python
import httpx

async def run(target: str) -> dict:
    return {"status": "success", "data": {"example": "OK"}}
```

## Catatan Final

Struktur ini menggabungkan semua kemampuan `core`, `modules`, dan `recon` ke dalam satu CLI modern yang lebih estetis, modular, dan mudah dikembangkan.
Jika kamu ingin menyimpan versi lama sebagai referensi, direktori `legacy/` sudah dibuat.
