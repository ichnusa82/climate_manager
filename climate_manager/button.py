"""Slot editor buttons: save, delete, delete all."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    zone = hass.data[DOMAIN]["zones"][entry.entry_id]
    async_add_entities(
        [
            SlotButton(entry, zone, "save", "mdi:content-save"),
            SlotButton(entry, zone, "delete", "mdi:delete"),
            SlotButton(entry, zone, "delete_all", "mdi:delete-sweep"),
        ]
    )


class SlotButton(ButtonEntity):
    """Pulsante per gestire le fasce orarie da dashboard."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(
        self, entry: ConfigEntry, zone, action: str, icon: str
    ) -> None:
        self._zone = zone
        self._action = action
        self._attr_translation_key = f"slot_{action}"
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_slot_{action}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
        )

    async def async_press(self) -> None:
        if self._action == "save":
            self._zone.save_editor(self.hass)
        elif self._action == "delete":
            self._zone.delete_selected(self.hass)
        else:
            self._zone.clear_all(self.hass)
