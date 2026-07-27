import socket
from unittest.mock import patch

import pytest

from app.errors import UnsafeUrlError
from app.services.urlguard import validate_url


def _addrinfo(ip: str):
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return [(family, socket.SOCK_STREAM, 6, "", (ip, 0))]


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost",
        "http://127.0.0.1",
        "http://192.168.0.1",
    ],
)
def test_rejects_loopback_and_private_addresses(url):
    with pytest.raises(UnsafeUrlError):
        validate_url(url)


def test_rejects_file_scheme():
    with pytest.raises(UnsafeUrlError):
        validate_url("file:///etc/passwd")


def test_rejects_ftp_scheme():
    with pytest.raises(UnsafeUrlError):
        validate_url("ftp://example.com/file")


def test_rejects_non_standard_port():
    with pytest.raises(UnsafeUrlError):
        validate_url("https://example.com:8080/")


def test_rejects_missing_hostname():
    with pytest.raises(UnsafeUrlError):
        validate_url("https:///path")


def test_allows_public_https():
    with patch("socket.getaddrinfo", return_value=_addrinfo("93.184.216.34")):
        assert validate_url("https://example.com/article") == "https://example.com/article"


def test_allows_standard_ports_explicitly():
    with patch("socket.getaddrinfo", return_value=_addrinfo("93.184.216.34")):
        validate_url("http://example.com:80/")
        validate_url("https://example.com:443/")
