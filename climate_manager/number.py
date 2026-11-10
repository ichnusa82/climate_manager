"""Single boiler setpoint shared by all thermostats using the same boiler."""
from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_BOILER_SETPOINT, DOMAIN, SETPOINT_MAX, SETPOINT_MIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    cfg = {**entry.data, **entry.options}
    boiler_sp = cfg.get(CONF_BOILER_SETPOINT)
    if not boiler_sp:
        return
    zone = hass.data[DOMAIN]["zones"][entry.entry_id]
    # un solo cursore attivo per caldaia: gli altri nascono disabilitati
    owners = hass.data[DOMAIN].setdefault("sp_owner", {})
    owner = owners.setdefault(boiler_sp, entry.entry_id)
    async_add_entities(
        [BoilerSetpointNumber(entry, zone, enabled=owner == entry.entry_id)]
    )


class BoilerSetpointNumber(RestoreNumber):
    """Gradi di setpoint della caldaia, validi per tutti i termostati."""

    _attr_has_entity_name = True
    _attr_translation_key = "boiler_setpoint"
    _attr_should_poll = False
    _attr_icon = "mdi:water-boiler"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = SETPOINT_MIN
    _attr_native_max_value = SETPOINT_MAX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, entry: ConfigEntry, zone, enabled: bool) -> None:
        self._zone = zone
        self._attr_unique_id = f"{entry.entry_id}_boiler_setpoint"
        self._attr_entity_registry_enabled_default = enabled
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
        )

    @property
    def native_value(self) -> float:
        return self._zone.shared["value"]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        shared = self._zone.shared
        shared["numbers"].add(self)
        self.async_on_remove(lambda: shared["numbers"].discard(self))
        if not shared["ready"]:
            last = await self.async_get_last_number_data()
            if last is not None and last.native_value is not None:
                shared["value"] = min(
                    SETPOINT_MAX, max(SETPOINT_MIN, float(last.native_value))
                )
            shared["ready"] = True
        self.async_write_ha_state()
        for zone in list(shared["zones"]):
            zone.notify(self.hass)

    async def async_set_native_value(self, value: float) -> None:
        shared = self._zone.shared
        shared["value"] = float(value)
        for number in list(shared["numbers"]):
            number.async_write_ha_state()
        for zone in list(shared["zones"]):
            zone.notify(self.hass)
