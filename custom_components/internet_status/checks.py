"""The three checks: ping, DNS and public IP. No Home Assistant objects here."""
from __future__ import annotations

import asyncio
import ipaddress
import json
import random
import re
import socket
import struct
import time
from dataclasses import dataclass

from icmplib import SocketPermissionError, async_ping

RCODES = {1: "format error", 2: "server failure", 3: "name does not exist", 4: "not implemented", 5: "refused"}


def split_hosts(text: str) -> list[str]:
    """'1.1.1.1, 9.9.9.9' -> ['1.1.1.1', '9.9.9.9']."""
    return [h for h in re.split(r"[\s,;]+", text or "") if h]


async def can_ping_privileged() -> bool | None:
    """True: raw ICMP sockets, False: unprivileged ICMP sockets, None: no ICMP at all."""
    for privileged in (True, False):
        try:
            await async_ping("127.0.0.1", count=0, timeout=0, privileged=privileged)
        except SocketPermissionError:
            continue
        return privileged
    return None


@dataclass
class PingResult:
    online: bool
    round_trip: float | None  # ms, average of the best answering host
    packet_loss: float  # %, of the best answering host
    host: str | None


async def ping_hosts(hosts: list[str], privileged: bool) -> PingResult:
    """Online when any host answers; round trip and loss of the best one."""

    async def one(host: str):
        try:
            return await async_ping(host, count=3, interval=0.2, timeout=2, privileged=privileged)
        except Exception:  # noqa: BLE001 - unresolvable name, network unreachable: not alive
            return None

    alive = [r for r in await asyncio.gather(*(one(h) for h in hosts)) if r is not None and r.is_alive]
    if not alive:
        return PingResult(False, None, 100.0, None)
    best = min(alive, key=lambda r: (r.packet_loss, r.avg_rtt))
    return PingResult(True, round(best.avg_rtt, 1), round(best.packet_loss * 100, 1), best.address)


class _DnsProtocol(asyncio.DatagramProtocol):
    def __init__(self, query_id: int, answer: asyncio.Future) -> None:
        self.query_id = query_id
        self.answer = answer

    def datagram_received(self, data: bytes, addr) -> None:
        if len(data) >= 12 and struct.unpack(">H", data[:2])[0] == self.query_id and not self.answer.done():
            self.answer.set_result(data)

    def error_received(self, exc: Exception) -> None:
        if not self.answer.done():
            self.answer.set_exception(exc)


async def dns_query(server: str, name: str, timeout: float = 2.0) -> tuple[float, int, int]:
    """Ask `server` for the A record of `name`: (response time in ms, rcode, number of answers)."""
    query_id = random.randrange(65536)
    labels = b"".join(bytes([len(p)]) + p for p in name.strip(".").encode("idna").split(b"."))
    packet = struct.pack(">HHHHHH", query_id, 0x0100, 1, 0, 0, 0) + labels + b"\0" + struct.pack(">HH", 1, 1)
    loop = asyncio.get_running_loop()
    answer: asyncio.Future = loop.create_future()
    family = socket.AF_INET6 if ":" in server else socket.AF_INET
    transport, _ = await loop.create_datagram_endpoint(
        lambda: _DnsProtocol(query_id, answer), remote_addr=(server, 53), family=family
    )
    try:
        start = time.monotonic()
        transport.sendto(packet)
        data = await asyncio.wait_for(answer, timeout)
        elapsed = (time.monotonic() - start) * 1000
    finally:
        transport.close()
    flags, answers = struct.unpack(">H", data[2:4])[0], struct.unpack(">H", data[6:8])[0]
    return elapsed, flags & 0xF, answers


@dataclass
class DnsResult:
    ok: bool
    server: str
    response_time: float | None  # ms
    error: str | None


async def check_dns(server: str, name: str) -> DnsResult:
    """The server answers with an address for `name`; one retry, UDP can drop a packet."""
    error = "no answer"
    for _ in range(2):
        try:
            ms, rcode, answers = await dns_query(server, name)
        except TimeoutError:
            error = "no answer"
            continue
        except OSError as err:
            error = err.strerror or str(err)
            continue
        if rcode == 0 and answers:
            return DnsResult(True, server, round(ms, 1), None)
        return DnsResult(False, server, round(ms, 1), RCODES.get(rcode, f"error {rcode}") if rcode else "no address")
    return DnsResult(False, server, None, error)


def parse_ip(text: str) -> str:
    """The address in a plain-text or JSON ({"ip": ...}) answer."""
    text = text.strip()
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if isinstance(data, dict):
        text = str(data.get("ip") or data.get("address") or "")
    return str(ipaddress.ip_address(text.split()[0] if text else ""))


def nameservers_from_network_info(info: dict) -> list[str]:
    """DNS servers from the Supervisor's /network/info, primary interface first."""
    servers: list[str] = []
    for iface in sorted(info.get("interfaces", []), key=lambda i: not i.get("primary")):
        for family in ("ipv4", "ipv6"):
            for server in (iface.get(family) or {}).get("nameservers") or []:
                server = server.split("/")[0]
                if server not in servers:
                    servers.append(server)
    return servers


def nameservers_from_resolv_conf(text: str) -> list[str]:
    return [line.split()[1] for line in text.splitlines() if line.startswith("nameserver") and len(line.split()) > 1]
