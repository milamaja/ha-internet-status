"""Ping, packet loss, DNS response time and public IP sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import InternetStatusConfigEntry
from .entity import InternetStatusEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: InternetStatusConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = entry.runtime_data
    entities: list[SensorEntity] = []
    if data.ping:
        entities += [PingSensor(data.ping, entry, "ping"), PacketLossSensor(data.ping, entry, "packet_loss")]
    entities.append(DnsResponseTimeSensor(data.dns, entry, "dns_response_time"))
    if data.public_ip:
        entities.append(PublicIpSensor(data.public_ip, entry, "public_ip"))
    async_add_entities(entities)


class _Milliseconds(InternetStatusEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_suggested_display_precision = 0


class PingSensor(_Milliseconds):
    """Average round trip to the best answering host; unknown while offline."""

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.round_trip


class PacketLossSensor(InternetStatusEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0

    @property
    def native_value(self) -> float:
        return self.coordinator.data.packet_loss


class DnsResponseTimeSensor(_Milliseconds):
    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.response_time


class PublicIpSensor(InternetStatusEntity, SensorEntity):
    @property
    def native_value(self) -> str:
        return self.coordinator.data

    @property
    def extra_state_attributes(self) -> dict:
        return {"service": self.coordinator.service}
