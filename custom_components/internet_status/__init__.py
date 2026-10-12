"""Internet Status: is the internet up, does DNS answer, and what is the public IP."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from aiohttp import web

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .checks import can_ping_privileged, split_hosts
from .const import (
    CONF_DNS_INTERVAL,
    CONF_DNS_NAME,
    CONF_DNS_SERVER,
    CONF_IP_INTERVAL,
    CONF_IP_SERVICE,
    CONF_IP_URL,
    CONF_PING_HOSTS,
    CONF_PING_INTERVAL,
    DEFAULTS,
    DOMAIN,
    IP_SERVICE_CUSTOM,
    IP_SERVICES,
)
from .coordinator import DnsCoordinator, InternetStatusData, PingCoordinator, PublicIpCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

CARD_URL = f"/{DOMAIN}/internet-status-card.js"
CARD_FILE = Path(__file__).parent / "frontend" / "internet-status-card.js"
PRIVILEGED = f"{DOMAIN}_privileged"

_LOGGER = logging.getLogger(__name__)

type InternetStatusConfigEntry = ConfigEntry[InternetStatusData]


class InternetStatusCardView(HomeAssistantView):
    """Serve the dashboard card without long-lived browser caching."""

    url = CARD_URL
    name = f"{DOMAIN}:card"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def get(self, request: web.Request) -> web.Response:
        body = await self._hass.async_add_executor_job(CARD_FILE.read_bytes)
        return web.Response(body=body, content_type="text/javascript", headers={"Cache-Control": "no-cache"})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the card and load it in the frontend."""
    body = await hass.async_add_executor_job(CARD_FILE.read_bytes)
    # A new version gets a new URL, so browsers never run a stale copy.
    url = f"{CARD_URL}?v={hashlib.sha1(body).hexdigest()[:10]}"
    hass.http.register_view(InternetStatusCardView(hass))
    # Loaded by the start page in up-to-date browsers. The dashboard resource
    # (added per entry below) covers clients holding a cached start page, such
    # as the companion apps and kiosk apps.
    add_extra_js_url(hass, url)
    hass.data[DOMAIN] = url
    return True


def settings(entry: ConfigEntry) -> dict:
    """The entry's settings: options over data over defaults."""
    return {**DEFAULTS, **entry.data, **entry.options}


async def async_setup_entry(hass: HomeAssistant, entry: InternetStatusConfigEntry) -> bool:
    """Start the checks."""
    conf = settings(entry)
    if PRIVILEGED not in hass.data:
        hass.data[PRIVILEGED] = await can_ping_privileged()
    privileged = hass.data[PRIVILEGED]
    hosts = split_hosts(conf[CONF_PING_HOSTS])
    ping = None
    if privileged is None:
        _LOGGER.error("Home Assistant may not send pings (ICMP) on this system; the internet check is off")
    elif hosts:
        ping = PingCoordinator(hass, entry, hosts, int(conf[CONF_PING_INTERVAL]), privileged)
    dns = DnsCoordinator(hass, entry, conf[CONF_DNS_SERVER].strip(), conf[CONF_DNS_NAME].strip(), int(conf[CONF_DNS_INTERVAL]))
    service = conf[CONF_IP_SERVICE]
    url = conf[CONF_IP_URL].strip() if service == IP_SERVICE_CUSTOM else IP_SERVICES.get(service)
    public_ip = PublicIpCoordinator(hass, entry, url, int(conf[CONF_IP_INTERVAL])) if url else None
    # A failing check makes its entities unavailable; it does not stop the others.
    for coordinator in (ping, dns, public_ip):
        if coordinator:
            await coordinator.async_refresh()
    entry.runtime_data = InternetStatusData(ping, dns, public_ip, hosts)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await _async_ensure_resource(hass, hass.data[DOMAIN])
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: InternetStatusConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _storage_resources(hass: HomeAssistant):
    """The dashboard resource collection, or None in YAML resource mode."""
    data = hass.data.get(LOVELACE_DATA)
    # resource_mode exists since Home Assistant 2026.x; older versions use mode.
    mode = getattr(data, "resource_mode", getattr(data, "mode", None)) if data else None
    if data is None or mode != "storage":
        return None
    return data.resources


async def _async_ensure_resource(hass: HomeAssistant, url: str) -> None:
    resources = _storage_resources(hass)
    if resources is None:
        _LOGGER.debug("Dashboard resources are in YAML mode; add %s yourself", url)
        return
    try:
        await resources.async_get_info()  # loads the collection
        for item in resources.async_items():
            if item.get("url", "").split("?")[0] == CARD_URL:
                if item["url"] != url:
                    await resources.async_update_item(item["id"], {"res_type": "module", "url": url})
                return
        await resources.async_create_item({"res_type": "module", "url": url})
    except Exception as err:  # noqa: BLE001 - the card still loads via the start page
        _LOGGER.warning("Could not register the Internet Status card as a dashboard resource: %s", err)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the dashboard resource when the integration is deleted."""
    resources = _storage_resources(hass)
    if resources is None:
        return
    try:
        await resources.async_get_info()
        for item in resources.async_items():
            if item.get("url", "").split("?")[0] == CARD_URL:
                await resources.async_delete_item(item["id"])
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not remove the Internet Status dashboard resource: %s", err)
