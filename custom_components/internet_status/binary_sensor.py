"""Online and DNS: connectivity binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import InternetStatusConfigEntry
from .entity import InternetStatusEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: InternetStatusConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = entry.runtime_data
    entities: list[BinarySensorEntity] = [DnsBinarySensor(data.dns, entry, "dns")]
    if data.ping:
        entities.insert(0, OnlineBinarySensor(data.ping, entry, "online"))
    async_add_entities(entities)


class OnlineBinarySensor(InternetStatusEntity, BinarySensorEntity):
    """On when one of the ping hosts answers."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.online

    @property
    def extra_state_attributes(self) -> dict:
        return {"hosts": self.coordinator.hosts}


class DnsBinarySensor(InternetStatusEntity, BinarySensorEntity):
    """On when the DNS server answers with an address for the test name."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.ok

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        return {"server": data.server, "test_name": self.coordinator.test_name, "error": data.error}
