# Uplink LAN di Fiberhome HG6145D2 & HG6145F1 via HTB Media Converter — Tanpa OLT

Panduan panjang lebar: cara mengaktifkan **uplink port LAN** pada ONT **Fiberhome HG6145D2** & **HG6145F1** (firmware RP4423) memakai **custom webui**, lalu menyambungkan ke jaringan utama lewat **media converter HTB** (fiber ↔ RJ45) — **tanpa OLT / tanpa GPON**.

**Kapan panduan ini dipakai?**
Anda punya 2 lokasi terhubung kabel fiber tapi **tidak ada OLT** di sisi Anda. Fiber tersebut tidak dipakai untuk GPON, melainkan dijembatani fiber ↔ RJ45 oleh sepasang media converter HTB, sementara ONT dipakai lewat port LAN-nya.

> ⚠️ **DISCLAIMER & BATASAN**
> - Hanya untuk perangkat **milik Anda sendiri / aset ISP yang Anda kelola secara resmi**. Memakai ini pada perangkat orang lain tanpa izin adalah ilegal di mana pun.
> - Ini **bukan** produk resmi Fiberhome. Semua merek adalah milik pemegang trademark masing-masing.
> - Flash/modifikasi firmware **berisiko brick** perangkat. Lakukan dengan risiko sendiri.
> - Panduan default diverifikasi pada firmware **RP4423** (perangkat yang beredar di Algeria). Firmware lain **belum terverifikasi** — nama menu bisa berbeda.
> - File `custom-webui.bin` & `custom-webui.sh` adalah karya **numberonedz** (lisensi MIT) — disertakan di folder `files/` dengan atribusi.

## Topologi

```
┌─────────────┐       RJ45       ┌───────────────┐   fiber    ┌───────────────┐       RJ45      ┌──────────────────────┐
│ Router/ISP  │◄───────────────►│ HTB #1        │◄═══════════►│ HTB #2        │◄──────────────►│ LAN1 HG6145F1/D2     │
│ (NOC utama) │   (LAN uplink)  │ Media         │  single/    │ Media         │   (LAN uplink) │ (port uplink)        │
└─────────────┘                 │ Converter     │  multimode  │ Converter     │                └──────────────────────┘
                                └───────────────┘             └───────────────┘
```

**Prinsip:** HTB media converter #1 & #2 dihubungkan kabel fiber (SC/UPC atau FC sesuai model). Sisi router utama ke HTB #1, sisi ONT ke HTB #2. Port LAN pada ONT dikonfigurasi sebagai **uplink/Ethernet WAN** (atau bridge/route sesuai kemampuan firmware) agar ONT memperoleh akses internet dari sisi utama.

## Perangkat & bahan

| Nama | Keterangan |
|---|---|
| Fiberhome HG6145F1 / HG6145D2 | ONT GPON, firmware **RP4423** |
| HTB Media Converter (2 buah) | Sepasang, fiber ↔ RJ45 (cek mode: single/multimode, wavelength 1310/1550, jarak 20 km dst) |
| Kabel fiber | Sesuai konektor HTB (SC/FC/ST) |
| Patch cord UTP | RJ45 |
| PC | Untuk membuka web interface ONT |

## Bagian 1 — Unlock Custom Webui (fiberhome HG6145F1/D2)

Sumber: proyek *Fiberhome HG6145F1 Custom Webui* (numberonedz) — bundle di folder [`files/`](files/).

**Login awal** (default):
- URL: `http://192.168.1.1`
- Login: `admin` / `admin` atau user default perangkat (cek label belakang ONT)

**Metode 1 — via Web interface (paling mudah):**
1. Buka `Management > Device Management > Local Upgrade`
2. Pilih file `files/custom-webui.bin` → `Update File`
3. Tunggu beberapa detik → muncul pesan **"Upgrade failed"** (itu normal — patch berbasis "failed upgrade" seperti push TR-069/OMCI)
4. **Refresh** halaman → halaman custom webui aktif
   - Hasil modifikasi **tidak bertahan** setelah reboot — tapi setting yang diubah tetap tersimpan. Opsi persistence tersedia di WebUI Options.

**Metode 2 — via Telnet:**
1. Aktifkan telnet: ikuti [`docs/enable-telnet.md`](docs/enable-telnet.md) — `Security > ACL Settings`, login `gpon` / `Fh@XXXXXX` (`XXXXXX` = 6 karakter terakhir MAC)
2. Upload `custom-webui.sh` ke direktori writable (mis. `/var`) via USB/tftp
3. `chmod +x custom-webui.sh`
4. Jalankan script

**Patch TR-069 (opsional tapi disarankan):** lihat [`docs/disable-tr069.md`](docs/disable-tr069.md). Tanpa patch ini, TR-069 otomatis re-enable setiap reboot dan bisa mengembalikan/menimpa setting Anda.

**Decrypt/encrypt config file** (kalau perlu edit manual): pakai [fiberhome-config-utility](https://github.com/numberonedz/fiberhome-config-utility).

## Bagian 2 — Setting port LAN → uplink

**Status verifikasinya tidak seragam** — bagian ini menunggu konfirmasi dari firmware nyata (lihat bagian "Kontribusi"). Langkah umum:

1. Login ke **custom webui**.
2. Buka `Network > Broadband Settings > Internet Settings`.
3. Pada opsi **Connection Type**, cari mode **Ethernet/ETH** (bukan GPON/PON). Opsi inilah yang umumnya tersembunyi di firmware stock — custom webui membuka endpoint-nya.
4. Set **PPPoE** / **DHCP** / **Static IP** sesuai provisioning sisi utama.
5. `Apply` → tes status internet di ONT → colok HTB media converter ke port LAN1.

**Fallback bila tidak ada opsi Ethernet/ETH WAN:** sesuai dokumentasi resmi custom-webui, firmware ini tidak dijamin punya mode "LAN sebagai WAN". Media converter HTB tetap bekerja sebagai jembatan fiber↔RJ45; ONT barangkali hanya bisa dipakai sebagai switch L2 di port LAN-nya, **tidak** sebagai gateway internet tanpa GPON. Sampaikan hasil uji Anda lewat Issues (lihat di bawah).

## Bagian 3 — Setting HTB Media Converter

Poin umum media converter fiber (HTB atau sejenisnya):

| Parameter | Keterangan |
|---|---|
| Mode | Single-mode (SC, 20 km / 40 km) atau multi-mode (50/62.5 µm, 2 km) — **harus sepasang & sama** |
| Wavelength | 1310 nm atau 1310/1550 nm (WDM) — pasangan TX↔RX harus sesuai (1310→1550 atau 1550→1310) |
| Link status | LED PWR + LINK (fiber) + LNK/ACT (UTP) harus menyala hijau |
| Auto-negotiation | Umumnya auto; kalau gagal, set 100 Mbps Full Duplex di sisi LAN |
| Jarak | Jangan melebihi spesifikasi jarak |

**Urutan uji:**
1. Colok power HTB #1 & #2, tunggu LED aktif.
2. Sambung fiber, pastikan LED fiber menyala dua sisi.
3. HTB #1 → router utama; HTB #2 → LAN1 ONT.
4. Tes ping dari sisi utama ke ONT `192.168.1.1`.

## Troubleshooting

| Gejala | Kemungkinan & solusi |
|---|---|
| "Upgrade failed" saat flash custom webui | **Normal** — refresh halaman, webui langsung aktif |
| Setelah reboot kembali ke stock webui | Patch volatil — aktifkan opsi **persistence** di WebUI Options / pasang patch TR-069 |
| Telnet tidak mau connect | ACL belum diaktifkan / MAC whitelist / salah password `Fh@XXXXXX` |
| LED fiber HTB mati | Salah jenis (single↔multi), wavelength tertukar, atau fiber putus |
| ONT tidak dapat IP | Connection type masih GPON → harus diganti ETH/bridge; TR-069 menimpa setting → terapkan disable-tr069 |
| Web UI tidak mau terbuka | Pastikan `patched ajax binary` terpasang; coba factory reset lalu ulangi flash |

## Peringatan keamanan

- **Ganti password default** `gpon` / `Fh@XXXXXX` & `admin/admin` setelah unlock.
- Jangan ekspos interface manajemen ONT ke internet publik.
- Label MAC/serial jangan diunggah ke repo publik.

## Kontribusi & hasil uji

Repositori ini menunggu konfirmasi dari lapangan (firmware RP4423 & RP4423-like):

- Path menu **persis** untuk mode ETH/Ethernet WAN di `Broadband Settings`
- Perilaku ONT tanpa OLT (bridge vs route vs locked)
- Model HTB yang dipakai (wavelength, jarak, mode)

Buka tab **Issues** di repo ini (sertakan: model ONT, firmware, screenshot menu — **sensor dulu data sensitif**: MAC, PPPoE password, serial), atau kirim Pull Request.

## Kredit

- [numberonedz](https://github.com/numberonedz) — Custom Webui & fiberhome-config-utility (lisensi MIT, lihat [`LICENSE`](LICENSE))
- Di-host & dirawat oleh [Daffiyanet](https://github.com/Indra725)

## ☕ Dukung / Donasi

Kalau repo ini bermanfaat, dukung pengembangan proyek Daffiyanet:

- **Halaman donasi:** https://indra725.github.io/donasi/
- **QRIS:** scan dari semua e-wallet / m-banking (DAFFIYANET, Konter — NMID ID1025401523762)
- **E-Wallet (DANA / GoPay / OVO / ShopeePay):** **08516163719** a/n **Daffiyanet**
- **WhatsApp:** [wa.me/628516163719](https://wa.me/628516163719)
