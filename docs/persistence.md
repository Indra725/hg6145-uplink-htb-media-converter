# Persistensi pasca-unlock — apa yang permanen, apa yang tidak

**Fakta dari payload `custom-webui.sh` (firmware RP4423):**
esktraksi `tar -tzf` menunjukkan payload hanya berisi **30 file web UI** (patched `cgi-bin/ajax`, html/js/css/menu). **Tidak ada** hook boot (`rcS`, `rc.local`, `init.d`, `autorun`) — artinya unlock bekerja dengan **bind-mount** ke filesystem stock yang read-only.

## Tabel ringkas

| Kejadian | Custom WebUI | Settings (DNS, TR-069 off, dll) | Config/password |
|---|---|---|---|
| Reboot biasa | ❌ hilang — kembali ke stock UI | ✅ tetap (tersimpan di partisi config) | ✅ tetap |
| TR-069 auto re-enable tiap boot | n/a | ⚠️ bisa tertimpa — wajib patch disable-tr069 | — |
| Factory reset / reset paksa | ❌ | ❌ **semua hilang** | ❌ hilang |

> **Catatan jujur:** tidak ada cara "menulis permanen ke flash" dengan tool ini. Modifikasi selalu berada di layer overlay/bind-mount — root filesystem tetap stock.

## Checklist pasca-unlock (wajib, agar set & lupa)

1. **Unlock** dengan metode mana pun (bin / .sh / `auto-unlock.py`) → custom webui aktif
2. **Aktifkan "persistence across reboot"** di WebUI Options (opsi ini disebut tersedia upstream untuk RP4423 — aktifkan, lalu reboot & cek apakah custom UI kembali)
3. **Patch disable TR-069** — lihat [`docs/disable-tr069.md`](disable-tr069.md). Tanpa ini, TR-069 aktif lagi tiap boot dan bisa menimpa setting Anda
4. **Set DNS & parameter penting** lain sesuai kebutuhan
5. **Backup config akhir** (sekali saja):
   - Web UI → download config ONT
   - Dekripsi dengan [fiberhome-config-utility](https://github.com/numberonedz/fiberhome-config-utility)
   - Simpan di luar ONT sebagai milik pribadi (mis. `config-anda.xml`). **Jangan commit ke repo publik** — berisi PPPoE/WiFi password
   - Simpan juga versi terenkripsinya untuk upload ulang langsung

## Setelah factory reset / reset paksa

Semua hilang — **tidak ada yang bertahan**, termasuk "persistence across reboot". Urutan restore:

1. **Flash ulang** `files/custom-webui.bin` (andal: `Management > Device Management > Local Upgrade` → "Upgrade failed" → refresh)
2. **Upload config backup** Anda via web interface (enkripsi dulu bila baru diedit)
3. **Terapkan ulang disable-tr069**
4. Verifikasi: reboot → apakah custom UI kembali? TR-069 tetap off?

## Tips operasional

- Simpan `files/custom-webui.bin` + `custom-webui.sh` + backup config di **STB Anda** (`/opt/hg6145-uplink/`) — sudah jalan via service `hg6145-tools` & `hg6145-auto-unlock`. Setelah reset paksa, ONT tinggal wget lagi dari STB.
- Untuk kepraktisan: screenshot menu **WebUI Options** setelah persistence diaktifkan — bukti bahwa opsi itu tercentang (tampilan bisa beda di firmware lain).

## Yang TIDAK bisa dijanjikan

- Custom WebUI 100% tidak hilang setelah factory reset (mustahil — ROM kembali stock).
- Unlock sekali lalu lupa selamanya; tetap ada kemungkinan perlu reflash setelah reset atau upgrade firmware resmi.
