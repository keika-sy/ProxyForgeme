import pytest

from proxyforge.fetchers import parse_geonode, parse_text
from proxyforge.models import Proxy, dedupe


def test_parse_text_valid_lines():
    body = "1.2.3.4:8080\n  5.6.7.8:1080  \nnot-a-proxy\n10.0.0.1:99999\n"
    out = parse_text(body, "http")
    assert [(p.ip, p.port) for p in out] == [("1.2.3.4", 8080), ("5.6.7.8", 1080)]
    assert all(p.protocol == "http" for p in out)


def test_parse_text_empty():
    assert parse_text("", "socks5") == []


def test_parse_geonode():
    payload = {"data": [{"ip": "1.1.1.1", "port": "80"}, {"ip": "bad"}, {"ip": "2.2.2.2", "port": 443}]}
    out = parse_geonode(payload, "socks4")
    assert [(p.ip, p.port, p.protocol) for p in out] == [("1.1.1.1", 80, "socks4"), ("2.2.2.2", 443, "socks4")]


def test_dedupe_keeps_first():
    a = Proxy(ip="1.1.1.1", port=80, protocol="http")
    b = Proxy(ip="1.1.1.1", port=80, protocol="socks5")
    c = Proxy(ip="2.2.2.2", port=80, protocol="http")
    assert dedupe([a, b, c]) == [a, c]


def test_invalid_protocol_rejected():
    with pytest.raises(ValueError):
        Proxy(ip="1.1.1.1", port=80, protocol="gopher")


def test_roundtrip_dict():
    p = Proxy(ip="1.1.1.1", port=80, protocol="http", country="ID", anonymity="elite")
    assert Proxy.from_dict(p.to_dict()) == p
