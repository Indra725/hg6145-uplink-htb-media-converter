# Auto-unlock service di STB — deteksi ONT baru & unlock otomatis (LAN only)

`hg6145-auto-service.py` — daemon di STB/Armbian yang menyapu LAN tiap menit; tiap MAC baru terdeteksi, mencoba login telnet `gpon`/`Fh@XXXXXX` (password default Fiberhome); bila sukses → dapat menyusulkan unlock otomatis.

**Status: experimental — uji dulu di lingkungan Anda.**

## Cara kerja

1. Ping sweep `RANGE` (default auto dari interface default-route)
2. `ip neigh show` → perangkat L2 live terdeteksi
3. MAC baru (belum di `seen.json`) dianggap "perangkat baru"
4. `MODE=monitor` (default): dicatat, **tidak ada aksi**
5. `MODE=unlock`: port 23 → telnet `gpon`/`Fh@XXXXXX` → `enable` → `wget http://<IP-STB>:8080/custom-webui.sh` → `chmod +x` → jalankan → transcript dicatat ke `auto-unlock.log`

## Instalasi

```bash
# 1. Letakkan file repo ini di /opt/hg6145-uplink
#    (lihat docs/stb-server-install.md)
python3 /opt/hg6145-uplink/hg6145-auto-service.py --help

# 2. Buat /opt/hg6145-uplink/auto-unlock.conf
MODE=monitor
INTERVAL=60
RANGE=192.168.1.0/24
# OUIS=94:6B:,00:18:F8:
```

**Arti tiap parameter:**

| Key | Nilai | Fungsi |
|---|---|---|
| `MODE` | `monitor` (default) | hanya catat kandidat, aman |
|  | `unlock` | unlock otomatis tiap ONT terdeteksi |
| `INTERVAL` | detik (60) | jarak antar sweep |
| `RANGE` | CIDR | subnet yang disapu |
| `OUIS` | koma-prefix MAC | batasin kandidat ke vendor tertentu |

## systemd service

`/etc/systemd/system/hg6145-auto-unlock.service`:

```ini
[Unit]
Description=HG6145 auto-unlock watcher (LAN only)
After=network-online.target hg6145-tools.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/hg6145-uplink/hg6145-auto-service.py --conf /opt/hg6145-uplink/auto-unlock.conf
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now hg6145-auto-unlock
journalctl -u hg6145-auto-unlock -f
tail -f /opt/hg6145-uplink/auto-unlock.log
```

## Keamanan & batasan — PENTING

- **Default `MODE=monitor` dengan sengaja** — unlock otomatis hanya aktif kalau Anda set `MODE=unlock`.
- Gate tunggal = password default Fiberhome. Perangkat lain tidak tersentuh.
- **Jangan** expose service ini / ST Anda ke luar LAN. Jangan port-forward.
- Log berisi MAC/IP saja. Jangan commit `seen.json` & `auto-unlock.log` ke repo (berisi info perangkat).
- Bisa salah deteksi pada perangkat non-Fiberhome yang kebetulan memakai password default itu (jarang tapi mungkin) → pertimbangkan `OUIS=`.

## Untuk pengguna di jaringan lain

Repo ini **self-contained** — bekerja di jaringan mana pun, asalkan:

1. Clone repo (atau download zip) di PC/STB jaringan Anda
2. HTTP server lokal melayani `files/` (port 8080)
3. ONT & mesin itu satu LAN

Server STB `192.168.1.17:8080` **hanya jaringan pemilik STB** — bukan layanan publik.
