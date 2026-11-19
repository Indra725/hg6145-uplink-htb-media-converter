# Verifikasi fitur Uplink (LAN sebagai WAN) — HG6145F1/D2 firmware RP4423

**Status: belum teruji di unit nyata.** Dokumen ini berisi bukti teknis dari payload `custom-webui.sh` (firmware RP4423) — bukan klaim pemasaran. Semua path/endpoint ada di firmware stock; custom webui hanya membuka aksesnya.

## Bukti dari payload (apa yang pasti ada)

| Bukti | Lokasi | 
|---|---|
| Endpoint `get_uplink_info` & `set_uplink_info` | `cgi-bin/ajax` (patched → semua endpoint bisa diakses admin) |
| Parameter `uplink_type` (nilai: `dev.eth.1`, `dev.eth.2`, …) | `cgi-bin/ajax`, `js/broadband_inter.js` |
| Parameter `uplink_port`, `uplink_mode` | `cgi-bin/ajax` |
| `InternetGatewayDevice.DeviceInfo.X_FH_LanUplinkPort` | `cgi-bin/ajax` |
| `lan_status_%d`, `lan4_bound`, `Wan_Port_checkbox1..5` | `js/broadband_inter.js`, `html/broadband_inter.html` |
| File flag `/fhconf/multi_lan` (`dev.eth.LAN`) | `cgi-bin/ajax` — toggle LAN port ke mode "uplink/multi_lan" |
| Profil operator: `IDN_TELKOM`, `MY_TM`, `PH_PLDT`, `BZ_INTELBRAS`, `BZ_VERO`, `X_FH_*`, `X_CMCC_*`, `X_CU_*` | `js/broadband_inter.js` |
| Custom WebUI memanggil `get_uplink_info` utk men-disable LAN-checkbox port yang dipakai uplink | `js/broadband_inter.js` (`disable_lan()`) |

`uplink_type` berisi `dev.eth.N` = **port Ethernet yang dipakai sebagai uplink sistem**, bukan PON. Inilah fitur yang dipakai carrier (mis. Telkom Indonesia) untuk SKU "ONT jadi router/WiFi dengan WAN dari port Ethernet".

## Yang TIDAK ada di payload

- **Tidak ada halaman/menu "Uplink"** — `menu/sub_menu_admin_inter` tidak punya entri uplink; `broadband_inter.html` hanya punya opsi Enable/Disable.
- Jadi **tidak ada menu yang bisa diklik** untuk uplink. Setting dilakukan via endpoint langsung (masih resmi, lewat custom webui yang sudah unlock).

## Cara cek di perangkat nyata

1. Unlock (metode mana pun) → login admin
2. Buka halaman **Broadband Settings** → tekan **F12** → tab **Console**
3. Jalankan:
   ```js
   XHR.get("get_uplink_info", null, function(d){ console.log(JSON.stringify(d, null, 2)) })
   ```
4. Perhatikan `uplink_info.uplink_type` → `dev.eth.1` / `dev.eth.X` berarti fitur hidup
5. Screenshot hasilnya → laporkan di Issues (sensor data sensitif)

## Cara set (jika respons di atas masuk akal)

```js
XHR.post("set_uplink_info", { uplink_type: "dev.eth.1" }, function(d){ console.log(JSON.stringify(d)) })
```

> ⚠️ Format persis parameter (`uplink_mode`? `uplink_port`?) **belum terdokumentasi** — jangan tembak nilai acak; salah set bisa mengubah port mapping WAN/LAN (ONT bisa kehilangan akses). Rujuk file config asli (`usrconfig_conf`) yang didekripsi dulu via [fiberhome-config-utility](https://github.com/numberonedz/fiberhome-config-utility) dan cari `X_FH_LanUplinkPort` untuk melihat format value-nya.

## Port WAN checkboxes (Wan_Port_checkbox1-5)

Halaman Broadband punya checkbox bind service WAN ke port fisik — ini bagian dari arsitektur "port mapping" carrier. Port yang terikat uplink (`uplink_type`) otomatis dinonaktifkan dari sisi LAN (via `disable_lan()`).

## Kesimpulan jujur

- ✅ Fitur "uplink via port LAN/Ethernet" **ada di firmware** dan dapat dipanggil setelah unlock custom webui (semua endpoint terbuka).
- ⚠️ **Tidak terverifikasi fungsional** (perlu uji di unit nyata: apakah ONT benar-benar forward traffic tanpa OLT).
- ⚠️ **Tidak ada menu GUI khusus** — harus via console/curl mengikuti panduan di atas.
- 🔬 Uji di bench dulu: unlock → `get_uplink_info` → set → kabel ke HTB media converter → cek internet dari sisi utama.
