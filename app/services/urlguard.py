import ipaddress
import socket
from urllib.parse import urlsplit

from app.config import settings
from app.errors import UnsafeUrlError

ALLOWED_SCHEMES = ("http", "https")
ALLOWED_PORTS = (80, 443)


def validate_url(url: str) -> str:
    parts = urlsplit(url)

    if parts.scheme not in ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"許可されていないスキームです: {parts.scheme or '(なし)'}")

    hostname = parts.hostname
    if not hostname:
        raise UnsafeUrlError("ホスト名が指定されていません")

    if parts.port is not None and parts.port not in ALLOWED_PORTS:
        raise UnsafeUrlError(f"許可されていないポートです: {parts.port}")

    if not settings.allow_private_hosts:
        _check_resolves_to_public_address(hostname)

    return url


def _check_resolves_to_public_address(hostname: str) -> None:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"ホスト名を解決できません: {hostname}") from exc

    for info in infos:
        raw_ip = info[4][0].split("%", 1)[0]
        ip = ipaddress.ip_address(raw_ip)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise UnsafeUrlError(f"アクセスが許可されていないアドレスです: {ip}")
