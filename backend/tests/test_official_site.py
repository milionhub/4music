"""Web oficial: solo destinos públicos (la URL viene de datos editables por cualquiera; evita SSRF)."""

import ipaddress
import socket
import urllib.error
import urllib.request

import pytest

from app import sources
from app.sources import official_site_text  # la original: conftest la sustituye en el módulo

ADDRESSES = {
    "artist.example": ["93.184.216.34"],
    "router.example": ["192.168.1.1"],
    "mixed.example": ["93.184.216.34", "10.0.0.5"],
    "mapped.example": ["::ffff:127.0.0.1"],
}


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    def getaddrinfo(host, port, *args, **kwargs):
        if host in ADDRESSES:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in ADDRESSES[host]]
        try:  # literales IP: sin red
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (str(ipaddress.ip_address(host)), port))]
        except ValueError:
            raise socket.gaierror("desconocido") from None
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


@pytest.mark.parametrize("url", ["https://artist.example/", "http://93.184.216.34:8080/bio"])
def test_public_destinations_allowed(url):
    assert sources._public_url(url)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8000/v1/artists", "http://localhost/", "http://192.168.1.1/", "http://router.example/",
    "http://169.254.169.254/latest/meta-data/", "http://[::1]/", "http://mapped.example/", "http://mixed.example/",
    "http://0.0.0.0/", "file:///etc/passwd", "ftp://artist.example/", "http:///nohost", "http://unknown.example/",
])
def test_private_or_invalid_destinations_rejected(url):
    assert not sources._public_url(url)


def test_private_url_is_never_requested(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("no debe haber petición")
    monkeypatch.setattr(sources._official_opener, "open", fail)
    assert official_site_text("http://192.168.1.1/", "ua") is None


def test_redirect_to_private_address_blocked():
    req = urllib.request.Request("https://artist.example/")
    with pytest.raises(urllib.error.URLError):
        sources._PublicRedirects().redirect_request(req, None, 302, "Found", {}, "http://127.0.0.1:8000/")
    assert sources._PublicRedirects().redirect_request(req, None, 302, "Found", {}, "https://artist.example/es") is not None
