"""One coordinator per check, each with its own interval."""
from __future__ import annotations

import logging
import os
import socket
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .checks import (
    DnsResult,
    PingResult,
    check_dns,
    nameservers_from_network_info,
    nameservers_from_resolv_conf,
    parse_ip,
    ping_hosts,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DETECT_EVERY = 600  # seconds between looking up the network's DNS server again


class PingCoordinator(DataUpdateCoordinator[PingResult]):
    """Is the internet reachable, and how fast."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, hosts: list[str], seconds: int, privileged: bool) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} ping", update_interval=timedelta(seconds=seconds))
        self.hosts = hosts
        self.privileged = privileged

    async def _async_update_data(self) -> PingResult:
        return await ping_hosts(self.hosts, self.privileged)


class DnsCoordinator(DataUpdateCoordinator[DnsResult]):
    """Does the DNS server answer."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, server: str, test_name: str, seconds: int) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} dns", update_interval=timedelta(seconds=seconds))
        self.fixed_server = server
        self.test_name = test_name
        self._detected: str | None = None
        self._detected_at = 0.0

    async def _async_update_data(self) -> DnsResult:
        server = self.fixed_server or await self._network_dns_server()
        if not server:
            raise UpdateFailed("No DNS server found; set one in the Internet Status options")
        return await check_dns(server, self.test_name)

    async def _network_dns_server(self) -> str | None:
        if self._detected and time.monotonic() - self._detected_at < DETECT_EVERY:
            return self._detected
        servers = await async_detect_dns_servers(self.hass)
        if servers:
            self._detected, self._detected_at = servers[0], time.monotonic()
        return self._detected


async def async_detect_dns_servers(hass: HomeAssistant) -> list[str]:
    """The DNS servers the network hands out (DHCP), as far as Home Assistant can see them.

    Home Assistant OS and Supervised: the host's network settings from the Supervisor
    (the core itself resolves through the Supervisor's own DNS, which is not what we
    want to test). Other installations: the system's resolv.conf.
    """
    supervisor, token = os.environ.get("SUPERVISOR"), os.environ.get("SUPERVISOR_TOKEN")
    if supervisor and token:
        try:
            session = async_get_clientsession(hass)
            async with session.get(
                f"http://{supervisor}/network/info",
                headers={"Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                servers = nameservers_from_network_info((await resp.json()).get("data", {}))
            if servers:
                return servers
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug("Could not read the network settings from the Supervisor: %s", err)
    try:
        text = await hass.async_add_executor_job(Path("/etc/resolv.conf").read_text)
    except OSError:
        return []
    return nameservers_from_resolv_conf(text)


class PublicIpCoordinator(DataUpdateCoordinator[str]):
    """The public IPv4 address of the connection."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, url: str, minutes: int) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} public ip", update_interval=timedelta(minutes=minutes))
        self.url = url
        self.service = urlparse(url).hostname or url

    async def _async_update_data(self) -> str:
        # IPv4 on purpose: with IPv6 every device has its own address, IPv4 is the connection's.
        session = async_get_clientsession(self.hass, family=socket.AF_INET)
        try:
            async with session.get(self.url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                resp.raise_for_status()
                text = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"No answer from {self.service}: {err}") from err
        try:
            return parse_ip(text)
        except ValueError as err:
            raise UpdateFailed(f"{self.service} did not answer with an IP address") from err


@dataclass
class InternetStatusData:
    ping: PingCoordinator | None
    dns: DnsCoordinator
    public_ip: PublicIpCoordinator | None
    ping_hosts: list[str]
