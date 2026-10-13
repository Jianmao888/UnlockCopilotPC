#!/usr/bin/env python3
"""
mitm_wu.py — 本地 MITM 代理，用于抓取 Windows Update / Store 的 SOAP 明文

设计要点：
  * 只对「微软更新/商店」相关域名做 TLS 中间人，其余域名原样隧道转发
    （避免影响用户正常上网）
  * CA 和叶子证书在本地生成，CA 装进 **当前用户** 根证书存储（不需要管理员）
  * 捕获到的请求/响应体写入 capture-mitm/

用法：
  python mitm_wu.py --gen-ca            # 只生成 CA（供 certutil 导入）
  python mitm_wu.py                     # 启动代理
"""
import argparse
import os
import socket
import ssl
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

HERE = os.path.dirname(os.path.abspath(__file__))
CADIR = os.path.join(HERE, "mitm-ca")
OUTDIR = os.path.join(HERE, "capture-mitm")
os.makedirs(CADIR, exist_ok=True)
os.makedirs(OUTDIR, exist_ok=True)

CA_KEY = os.path.join(CADIR, "ca.key")
CA_CRT = os.path.join(CADIR, "ca.crt")

# 这些域名做中间人
INTERCEPT_SUFFIXES = (
    "microsoft.com",
    "windowsupdate.com",
    "delivery.mp.microsoft.com",
    "update.microsoft.com",
    "mp.microsoft.com",
    "live.com",
)
KEYWORDS = (
    "SoftwareDistribution", "SyncUpdates", "ProductsParameters",
    "DeviceAttributes", "GetCookie", "ClientWebService",
    "<Products", "CallerAttributes", "AppCategoryIds",
)

LISTEN = ("127.0.0.1", 8899)
_seq = 0
_lock = threading.Lock()


def log(*a):
    print(f"[{datetime.now().strftime('%H:%M:%S')}]", *a, flush=True)


# ---------------------------------------------------------------- CA / 证书
def load_or_make_ca():
    if os.path.exists(CA_KEY) and os.path.exists(CA_CRT):
        key = serialization.load_pem_private_key(open(CA_KEY, "rb").read(), password=None)
        crt = x509.load_pem_x509_certificate(open(CA_CRT, "rb").read())
        return key, crt

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "DSH WU Capture CA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Local Capture"),
    ])
    now = datetime.now(timezone.utc)
    crt = (x509.CertificateBuilder()
           .subject_name(name).issuer_name(name)
           .public_key(key.public_key())
           .serial_number(x509.random_serial_number())
           .not_valid_before(now - timedelta(days=1))
           .not_valid_after(now + timedelta(days=3650))
           .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
           .sign(key, hashes.SHA256()))
    open(CA_KEY, "wb").write(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    open(CA_CRT, "wb").write(crt.public_bytes(serialization.Encoding.PEM))
    return key, crt


CA_KEY_OBJ, CA_CRT_OBJ = load_or_make_ca()
_leaf_cache = {}
_leaf_lock = threading.Lock()


def leaf_for(host):
    with _leaf_lock:
        if host in _leaf_cache:
            return _leaf_cache[host]
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = datetime.now(timezone.utc)
        crt = (x509.CertificateBuilder()
               .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)]))
               .issuer_name(CA_CRT_OBJ.subject)
               .public_key(key.public_key())
               .serial_number(x509.random_serial_number())
               .not_valid_before(now - timedelta(days=1))
               .not_valid_after(now + timedelta(days=825))
               .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
               .sign(CA_KEY_OBJ, hashes.SHA256()))
        _leaf_cache[host] = (key, crt)
        return _leaf_cache[host]


def should_intercept(host):
    h = host.lower().split(":")[0]
    return any(h == s or h.endswith("." + s) for s in INTERCEPT_SUFFIXES)


def save(kind, host, data):
    global _seq
    with _lock:
        _seq += 1
        n = _seq
    fn = f"{n:03d}-{kind}-{host.replace(':','_')}.txt"
    p = os.path.join(OUTDIR, fn)
    with open(p, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("utf-8", "replace"))
    return fn


# ---------------------------------------------------------------- 代理
def read_headers(sock):
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            return None, None
        buf += chunk
        if len(buf) > 65536:
            return None, None
    head, _, rest = buf.partition(b"\r\n\r\n")
    return head.decode("latin-1"), rest


def tunnel(a, b):
    try:
        while True:
            data = a.recv(65536)
            if not data:
                break
            b.sendall(data)
    except Exception:
        pass
    finally:
        for s in (a, b):
            try:
                s.close()
            except Exception:
                pass


def handle(conn, addr):
    try:
        head, rest = read_headers(conn)
        if not head:
            conn.close()
            return
        lines = head.split("\r\n")
        parts = lines[0].split()
        if len(parts) < 3:
            conn.close()
            return
        method, target, _ver = parts[0], parts[1], parts[2]

        if method.upper() == "CONNECT":
            host, _, port = target.partition(":")
            port = int(port or 443)
            if not should_intercept(host):
                up = socket.create_connection((host, port), timeout=20)
                conn.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                t = threading.Thread(target=tunnel, args=(conn, up), daemon=True)
                t.start()
                tunnel(up, conn)
                return

            # --- MITM ---
            log(f"CONNECT(拦截) {host}:{port}")
            conn.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            key, crt = leaf_for(host)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(*_pem_tmp(key, crt, host))
            try:
                tls = ctx.wrap_socket(conn, server_side=True)
            except Exception as e:
                log(f"  TLS 握手失败: {e}")
                conn.close()
                return
            upstream = socket.create_connection((host, port), timeout=20)
            uctx = ssl.create_default_context()
            uctx.check_hostname = False
            uctx.verify_mode = ssl.CERT_NONE
            utls = uctx.wrap_socket(upstream, server_hostname=host)
            pump(tls, utls, host)
            return

        # --- 明文 HTTP ---
        host, _, port = target.partition(":")
        port = int(port or 80)
        log(f"HTTP {method} {target}")
        up = socket.create_connection((host, port), timeout=20)
        up.sendall(head.encode("latin-1") + b"\r\n\r\n" + (rest or b""))
        pump(conn, up, host)
    except Exception as e:
        log(f"处理失败 {addr}: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


_tmp_lock = threading.Lock()


def _pem_tmp(key, crt, host):
    """把 key/cert 写到该 host 专属的临时文件（ssl 需要文件路径）。"""
    safe = host.replace(":", "_").replace("*", "_")
    with _tmp_lock:
        kp = os.path.join(CADIR, f"_leaf-{safe}.key")
        cp = os.path.join(CADIR, f"_leaf-{safe}.crt")
        open(kp, "wb").write(key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
        open(cp, "wb").write(crt.public_bytes(serialization.Encoding.PEM))
    return cp, kp


def pump(client, server, host):
    """双向转发并记录含关键词的数据。"""
    def c2s():
        buf = b""
        try:
            while True:
                d = client.recv(65536)
                if not d:
                    break
                buf += d
                server.sendall(d)
                if b"\r\n\r\n" in buf:
                    txt = buf.decode("utf-8", "replace")
                    hit = [k for k in KEYWORDS if k in txt]
                    if hit:
                        fn = save("req", host, buf)
                        body = txt.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in txt else ""
                        log(f"  *** 请求命中 {hit} -> {fn} ({len(buf)}B)")
                        log(f"      {body[:300]}")
                    buf = b""
        except Exception:
            pass
        finally:
            try: server.shutdown(socket.SHUT_WR)
            except Exception: pass

    def s2c():
        buf = b""
        try:
            while True:
                d = server.recv(65536)
                if not d:
                    break
                buf += d
                client.sendall(d)
                if len(buf) > 200 and (b"</" in buf or b"\r\n\r\n" in buf):
                    txt = buf.decode("utf-8", "replace")
                    if "SyncUpdates" in txt or "Products" in txt or "<s:Envelope" in txt or "<Envelope" in txt:
                        fn = save("resp", host, buf)
                        log(f"  *** 响应命中 -> {fn} ({len(buf)}B)")
                    buf = b""
        except Exception:
            pass
        finally:
            try: client.shutdown(socket.SHUT_WR)
            except Exception: pass

    t1 = threading.Thread(target=c2s, daemon=True)
    t2 = threading.Thread(target=s2c, daemon=True)
    t1.start(); t2.start()
    t1.join(); t2.join()
    try: client.close()
    except Exception: pass
    try: server.close()
    except Exception: pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-ca", action="store_true")
    a = ap.parse_args()
    if a.gen_ca:
        print(f"CA 已就绪: {CA_CRT}")
        return 0
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(LISTEN)
    srv.listen(200)
    log(f"MITM 代理监听 {LISTEN[0]}:{LISTEN[1]}")
    log(f"拦截域名: {', '.join(INTERCEPT_SUFFIXES)}")
    log(f"输出目录: {OUTDIR}")
    while True:
        try:
            conn, addr = srv.accept()
        except KeyboardInterrupt:
            break
        threading.Thread(target=handle, args=(conn, addr), daemon=True).start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
