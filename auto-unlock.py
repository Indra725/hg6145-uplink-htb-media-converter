#!/usr/bin/env python3
"""
auto-unlock.py — otomasi unlock Custom Webui pada Fiberhome HG6145F1 / HG6145D2
firmware RP4423 (dan sejenisnya) lewat telnet.

STATUS: EXPERIMENTAL — belum diuji di perangkat nyata oleh penulis.
Harap backup config ONT (web UI) SEBELUM menjalankan.

Cara kerja:
  1. Menghitung password telnet default: Fh@ + 6 hex terakhir dari MAC (uppercase).
  2. Menjalankan HTTP server lokal di PC (port 8080) untuk melayani custom-webui.sh.
  3. Telnet ke ONT (default 192.168.1.1), login gpon / Fh@XXXXXX, lalu `enable`.
  4. Mengirim perintah: wget custom-webui.sh dari PC -> chmod +x -> jalankan.
  5. Menampilkan semua output telnet agar bisa ditinjau manual.

Persiapan:
  * Python 3.6+ (tidak butuh dependency eksternal).
  * Telnet HARUS sudah diaktifkan lewat web UI  (Security > ACL Settings),
    lihat docs/enable-telnet.md.
  * PC Anda dan ONT harus dalam LAN yang sama (PC: 192.168.1.x).

Contoh:
  python auto-unlock.py --mac 94:6b:xx:xx:xx:xx
  python auto-unlock.py --mac 946bxxxxxxxx --ont-ip 192.168.1.1 --pc-ip 192.168.1.50
  python auto-unlock.py --mac 946bxxxxxxxx --dry-run
"""

import argparse
import functools
import http.server
import os
import re
import socket
import sys
import threading
import time

DEFAULT_ONT = '192.168.1.1'
DEFAULT_HTTP_PORT = 8080
TIMEOUT = 8  # detik, untuk tiap fase baca output


def mac_to_password(mac: str) -> str:
    """Fh@ + 6 hex terakhir MAC, uppercase."""
    hexpart = re.sub(r'[^0-9a-fA-F]', '', mac)
    if len(hexpart) < 6:
        raise ValueError('MAC tidak valid: %r' % mac)
    return 'Fh@' + hexpart[-6:].upper()


def find_custom_webui_sh() -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, 'files', 'custom-webui.sh')
    if not os.path.isfile(path):
        sys.exit('ERROR: files/custom-webui.sh tidak ditemukan di %s' % base)
    return path


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


def serve_files(directory: str, port: int):
    handler = functools.partial(QuietHandler, directory=directory)
    httpd = http.server.ThreadingHTTPServer(('', port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


class Telnet:
    """Client telnet minimal (tanpa dependency)."""

    IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240

    def __init__(self, host: str, port: int = 23):
        self.sock = socket.create_connection((host, port), timeout=TIMEOUT)
        self.sock.settimeout(1.0)
        self.buf = b''

    def _strip_iac(self, data: bytes) -> bytes:
        out = bytearray()
        i = 0
        while i < len(data):
            b = data[i]
            if b == self.IAC:
                if i + 1 < len(data) and data[i + 1] == self.IAC:
                    out.append(self.IAC)
                    i += 2
                    continue
                if i + 1 < len(data) and data[i + 1] == self.SB:
                    # suboption until IAC SE
                    j = i + 2
                    while j + 1 < len(data) and not (data[j] == self.IAC and data[j + 1] == self.SE):
                        j += 1
                    i = j + 2
                    continue
                if i + 2 < len(data):
                    i += 3
                    continue
                i += 2
                continue
            out.append(b)
            i += 1
        return bytes(out)

    def read_until(self, marker: bytes, timeout: int = TIMEOUT) -> bytes:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                time.sleep(0.1)
                continue
            if not chunk:
                break
            self.buf += self._strip_iac(chunk)
            idx = self.buf.find(marker)
            if idx != -1:
                out, self.buf = self.buf[:idx], self.buf[idx + len(marker):]
                return out
        out, self.buf = self.buf, b''
        return out

    def read_all(self, timeout: int = 6) -> bytes:
        out = bytearray()
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            out += self._strip_iac(chunk)
        return bytes(out)

    def send(self, text: str):
        self.sock.sendall(text.encode() + b'\r\n')

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser(description='Otomasi unlock HG6145F1/D2 via telnet (experimental)')
    ap.add_argument('--mac', required=True, help='MAC ONT, ex: 94:6b:12:ab:cd:ef atau 946b12abcdef')
    ap.add_argument('--ont-ip', default=DEFAULT_ONT, help='IP ONT (default: 192.168.1.1)')
    ap.add_argument('--pc-ip', default=None, help='IP PC di LAN ONT yang dipakai ONT mendownload script (auto-detect bila tidak diisi)')
    ap.add_argument('--http-port', type=int, default=DEFAULT_HTTP_PORT, help='Port HTTP lokal (default 8080)')
    ap.add_argument('--dry-run', action='store_true', help='Hanya tampilkan rencana & password, tanpa konek')
    args = ap.parse_args()

    password = mac_to_password(args.mac)
    sh_path = find_custom_webui_sh()
    pc_ip = args.pc_ip or socket.gethostbyname(socket.gethostname())

    print('=' * 64)
    print('HG6145F1/D2 auto unlock — EXPERIMENTAL')
    print('=' * 64)
    print('ONT IP      :', args.ont_ip)
    print('PC IP       :', pc_ip)
    print('Password    :', password)
    print('Script      :', sh_path)
    print('HTTP URL    : http://%s:%d/custom-webui.sh' % (pc_ip, args.http_port))
    print()

    if args.dry_run:
        print('[dry-run] tidak terhubung ke ONT. Rencana:')
        print('  1. HTTP server lokal melayani files/')
        print('  2. telnet %s -> gpon / %s' % (args.ont_ip, password))
        print('  3. enable -> %s' % password)
        print('  4. wget http://%s:%d/custom-webui.sh -O /var/custom-webui.sh' % (pc_ip, args.http_port))
        print('  5. chmod +x /var/custom-webui.sh && /var/custom-webui.sh')
        return

    httpd = serve_files(os.path.dirname(sh_path), args.http_port)
    print('[+] HTTP server jalan di port %d, tekan Ctrl+C untuk berhenti' % args.http_port)

    print('[+] Menghubungkan ke telnet %s ...' % args.ont_ip)
    t = Telnet(args.ont_ip)
    try:
        print(t.read_until(b'ogin:').decode(errors='ignore'))
        t.send('gpon')
        print(t.read_until(b'assword:').decode(errors='ignore'))
        t.send(password)
        banner = t.read_until(b'>', timeout=TIMEOUT)
        print(banner.decode(errors='ignore'))
        if b'User' in banner or b'>' in banner:
            t.send('enable')
            print(t.read_until(b'assword:').decode(errors='ignore'))
            t.send(password)
            print(t.read_all(timeout=4).decode(errors='ignore'))
        else:
            print('[!] Prompt tidak dikenali — lanjut mengirim wget apa adanya')

        cmds = [
            'wget http://%s:%d/custom-webui.sh -O /var/custom-webui.sh' % (pc_ip, args.http_port),
            'chmod +x /var/custom-webui.sh',
            '/var/custom-webui.sh',
        ]
        for cmd in cmds:
            print('\n>>> %s' % cmd)
            t.send(cmd)
            print(t.read_all(timeout=10).decode(errors='ignore'))

        print('\n[+] Selesai mengirim perintah unlock.')
        print('    Buka http://%s di browser Anda — jika muncul custom webui, unlock berhasil.' % args.ont_ip)
        print('    Jika TIDAK: periksa log di atas (perintah wget/busybox tidak dikenal?),')
        print('    lalu coba cara TFTP manual di wiki/dokumentasi perangkat.')
    finally:
        t.close()
        httpd.shutdown()


if __name__ == '__main__':
    main()
