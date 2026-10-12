"""Constants for Internet Status."""
from __future__ import annotations

DOMAIN = "internet_status"
NAME = "Internet Status"

CONF_PING_HOSTS = "ping_hosts"
CONF_PING_INTERVAL = "ping_interval"
CONF_DNS_SERVER = "dns_server"
CONF_DNS_NAME = "dns_name"
CONF_DNS_INTERVAL = "dns_interval"
CONF_IP_SERVICE = "public_ip_service"
CONF_IP_URL = "public_ip_url"
CONF_IP_INTERVAL = "public_ip_interval"

# Services that tell the public IP address of the connection, as plain text.
IP_SERVICES = {
    "ipify": "https://api.ipify.org",
    "mullvad": "https://ipv4.am.i.mullvad.net/ip",
}
IP_SERVICE_CUSTOM = "custom"
IP_SERVICE_NONE = "none"

DEFAULTS = {
    CONF_PING_HOSTS: "1.1.1.1, 9.9.9.9",
    CONF_PING_INTERVAL: 60,  # seconds
    CONF_DNS_SERVER: "",  # empty: the DNS server the network hands out
    CONF_DNS_NAME: "home-assistant.io",
    CONF_DNS_INTERVAL: 60,  # seconds
    CONF_IP_SERVICE: "ipify",
    CONF_IP_URL: "",
    CONF_IP_INTERVAL: 15,  # minutes
}
