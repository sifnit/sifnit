#!/usr/bin/env python3
"""Serve Product Camera over HTTPS on your local network with a self-signed certificate.

    python3 serve.py            # port 8443
    python3 serve.py 9000       # another port

The phone and this computer must be on the same Wi-Fi. Chrome shows a warning the first
time because the certificate is self-signed: tap Advanced, then Proceed.
"""
import datetime
import http.server
import ipaddress
import os
import shutil
import socket
import ssl
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CERT_DIR = HERE / ".cert"
CERT, KEY = CERT_DIR / "cert.pem", CERT_DIR / "key.pem"
IP_FILE = CERT_DIR / "ip.txt"


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent; this just picks the outward interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def make_cert_cryptography(ip):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Product Camera")])
    now = datetime.datetime.now(datetime.timezone.utc)
    san = x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address(ip)),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
    ])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=825))
            .add_extension(san, critical=False).sign(key, hashes.SHA256()))
    KEY.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption()))
    CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def make_cert_openssl(ip):
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
        "-keyout", str(KEY), "-out", str(CERT), "-days", "825", "-subj", "/CN=Product Camera",
        "-addext", f"subjectAltName=DNS:localhost,IP:{ip},IP:127.0.0.1",
    ], check=True, capture_output=True)


def ensure_cert(ip):
    # Reuse the certificate unless this computer's network address changed.
    if CERT.exists() and KEY.exists() and IP_FILE.exists() and IP_FILE.read_text().strip() == ip:
        return
    CERT_DIR.mkdir(exist_ok=True)
    try:
        make_cert_cryptography(ip)
    except ImportError:
        if not shutil.which("openssl"):
            sys.exit("Need either the 'cryptography' Python package or the openssl command to make a certificate.\n"
                     "Install it with:  pip install cryptography")
        make_cert_openssl(ip)
    IP_FILE.write_text(ip)
    print("Made a new self-signed certificate.")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(HERE), **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")  # always pick up app changes
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8443
    ip = lan_ip()
    ensure_cert(ip)
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT, KEY)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    print(f"\nProduct Camera is running.\n\n  On your phone, open:  https://{ip}:{port}\n")
    print("  Chrome will warn that the connection isn't private (the certificate is self-signed).")
    print("  Tap Advanced, then Proceed. Phone and computer must be on the same Wi-Fi.")
    print("\nPress Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
