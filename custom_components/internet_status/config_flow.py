"""Config and options flow for Internet Status."""
from __future__ import annotations

import ipaddress
import socket
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .checks import parse_ip, split_hosts
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
    IP_SERVICE_NONE,
    IP_SERVICES,
)
from .coordinator import async_detect_dns_servers

TITLE = "Internet"


def _seconds(minimum: int, maximum: int, unit: str) -> NumberSelector:
    return NumberSelector(NumberSelectorConfig(min=minimum, max=maximum, step=1, unit_of_measurement=unit, mode=NumberSelectorMode.BOX))


def _schema(values: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_PING_HOSTS, default=values[CONF_PING_HOSTS]): TextSelector(),
            vol.Required(CONF_PING_INTERVAL, default=values[CONF_PING_INTERVAL]): _seconds(10, 3600, "s"),
            vol.Optional(CONF_DNS_SERVER, description={"suggested_value": values[CONF_DNS_SERVER]}): TextSelector(),
            vol.Required(CONF_DNS_NAME, default=values[CONF_DNS_NAME]): TextSelector(),
            vol.Required(CONF_DNS_INTERVAL, default=values[CONF_DNS_INTERVAL]): _seconds(10, 3600, "s"),
            vol.Required(CONF_IP_SERVICE, default=values[CONF_IP_SERVICE]): SelectSelector(
                SelectSelectorConfig(
                    options=[*IP_SERVICES, IP_SERVICE_CUSTOM, IP_SERVICE_NONE],
                    translation_key=CONF_IP_SERVICE,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_IP_URL, description={"suggested_value": values[CONF_IP_URL]}): TextSelector(
                TextSelectorConfig(type=TextSelectorType.URL)
            ),
            vol.Required(CONF_IP_INTERVAL, default=values[CONF_IP_INTERVAL]): _seconds(1, 1440, "min"),
        }
    )


async def _async_validate(hass: HomeAssistant, user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Clean up the input; errors per field."""
    values = {
        **user_input,
        CONF_PING_HOSTS: ", ".join(split_hosts(user_input.get(CONF_PING_HOSTS, ""))),
        CONF_DNS_SERVER: (user_input.get(CONF_DNS_SERVER) or "").strip(),
        CONF_DNS_NAME: (user_input.get(CONF_DNS_NAME) or "").strip().strip("."),
        CONF_IP_URL: (user_input.get(CONF_IP_URL) or "").strip(),
        CONF_PING_INTERVAL: int(user_input[CONF_PING_INTERVAL]),
        CONF_DNS_INTERVAL: int(user_input[CONF_DNS_INTERVAL]),
        CONF_IP_INTERVAL: int(user_input[CONF_IP_INTERVAL]),
    }
    errors: dict[str, str] = {}
    if not values[CONF_PING_HOSTS]:
        errors[CONF_PING_HOSTS] = "invalid_hosts"
    if values[CONF_DNS_SERVER]:
        try:
            values[CONF_DNS_SERVER] = str(ipaddress.ip_address(values[CONF_DNS_SERVER]))
        except ValueError:
            errors[CONF_DNS_SERVER] = "invalid_dns_server"
    if not values[CONF_DNS_NAME] or " " in values[CONF_DNS_NAME]:
        errors[CONF_DNS_NAME] = "invalid_dns_name"
    if values[CONF_IP_SERVICE] == IP_SERVICE_CUSTOM:
        url = values[CONF_IP_URL]
        if not url.startswith(("http://", "https://")):
            errors[CONF_IP_URL] = "custom_url_required"
        else:
            try:
                session = async_get_clientsession(hass, family=socket.AF_INET)
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    resp.raise_for_status()
                    parse_ip(await resp.text())
            except (aiohttp.ClientError, TimeoutError, ValueError):
                errors[CONF_IP_URL] = "cannot_get_ip"
    return values, errors


async def _async_placeholders(hass: HomeAssistant) -> dict[str, str]:
    servers = await async_detect_dns_servers(hass)
    return {"detected": ", ".join(servers) if servers else "-"}


class InternetStatusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up Internet Status."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        values = dict(DEFAULTS)
        if user_input is not None:
            values, errors = await _async_validate(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title=TITLE, data=values)
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(values),
            errors=errors,
            description_placeholders=await _async_placeholders(self.hass),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return InternetStatusOptionsFlow()


class InternetStatusOptionsFlow(OptionsFlow):
    """Change any setting later; the integration reloads."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        values = {**DEFAULTS, **self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            values, errors = await _async_validate(self.hass, user_input)
            if not errors:
                return self.async_create_entry(data=values)
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(values),
            errors=errors,
            description_placeholders=await _async_placeholders(self.hass),
        )
