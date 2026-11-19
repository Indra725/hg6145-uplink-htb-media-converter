# Hosting tools unlock di STB (Armbian) — LAN only

Opsi menjalankan file server `custom-webui.sh` di STB Armbian Anda (mis. STB HG680P/HG680/HG6145), sehingga ONT bisa mengunduh langsung dari STB tanpa PC menyala.

**Teruji:** STB Armbian 6.x, Python 3.11.2, service `hg6145-tools` di port **8080**.

## Instalasi di STB

```bash
# 1. Upload direktori files/ isi repo ini ke /opt/hg6145-uplink
#    (dari PC Anda)
sftp> mkdir /opt/hg6145-uplink
#    letakkan custom-webui.sh & custom-webui.bin di sana, atau:
mkdir -p /opt/hg6145-uplink
# wget atau copy file custom-webui.sh & auto-unlock.py ke /opt/hg6145-uplink

# 2. Buat systemd service
cat > /etc/systemd/system/hg6145-tools.service <<'EOF'
[Unit]
Description=HG6145 uplink tools HTTP server (LAN only)
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 -m http.server 8080 --bind 0.0.0.0 -d /opt/hg6145-uplink
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now hg6145-tools
```

## Verifikasi

```bash
systemctl status hg6145-tools          # active (running)
curl -I http://127.0.0.1:8080/custom-webui.sh
md5sum /opt/hg6145-uplink/custom-webui.sh
```

Dari PC (harus HTTP 200):

```powershell
Invoke-WebRequest -Method Head http://<IP-STB>:8080/custom-webui.sh
```

## Pemakaian dari ONT

```
wget http://<IP-STB>:8080/custom-webui.sh -O /var/custom-webui.sh
chmod +x /var/custom-webui.sh && /var/custom-webui.sh
```

Atau via `auto-unlock.py` di PC/STB dengan `--pc-ip <IP-STB>`.

## Catatan keamanan

- Service ini melayani **seluruh isi `/opt/hg6145-uplink`** ke siapa pun di LAN.
- **Jangan** port-forward / ekspos port 8080 ke internet.
- Setelah unlock selesai, boleh `systemctl disable --now hg6145-tools`.
- Jangan simpan file kredensial (config ONT, backup) di folder ini.
