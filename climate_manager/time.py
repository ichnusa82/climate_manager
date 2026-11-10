"""Orari dell'editor delle fasce: "Dalle" e "Alle"."""
from __future__ import annotations

from datetime import time as dtime

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    zone = hass.data[DOMAIN]["zones"][entry.entry_id]
    async_add_entities(
        [
            SlotTime(entry, zone, "start", "mdi:clock-start"),
            SlotTime(entry, zone, "end", "mdi:clock-end"),
        ]
    )


class SlotTime(TimeEntity):
    """Orario di inizio o fine della fascia che si sta componendo."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(
        self, entry: ConfigEntry, zone, key: str, icon: str
    ) -> None:
        self._zone = zone
        self._key = key
        self._attr_translation_key = f"slot_{key}"
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_slot_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
        )

    @property
    def native_value(self) -> dtime:
        hours, minutes = self._zone.editor[self._key].split(":")
        return dtime(int(hours), int(minutes))

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._zone.editor_listeners.append(self._refresh)
        self.async_on_remove(lambda: self._zone.editor_listeners.remove(self._refresh))

    @callback
    def _refresh(self) -> None:
        self.async_write_ha_state()

    async def async_set_value(self, value: dtime) -> None:
        self._zone.editor[self._key] = value.strftime("%H:%M")
        self.async_write_ha_state()
