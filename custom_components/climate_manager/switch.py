"""Switches: valve enabled and day selectors of the slot editor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DAY_ORDER, DOMAIN, get_heaters


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    cfg = {**entry.data, **entry.options}
    heaters = get_heaters(cfg)
    zone = hass.data[DOMAIN]["zones"][entry.entry_id]

    entities: list[SwitchEntity] = []
    if len(heaters) >= 2:  # con una sola valvola non serve scegliere
        entities += [ValveEnableSwitch(hass, entry, zone, h) for h in heaters]
    entities += [SlotDaySwitch(entry, zone, key) for key in DAY_ORDER]
    async_add_entities(entities)


def _valve_label(hass: HomeAssistant, entity_id: str) -> str:
    """Nome stabile della valvola: non dipende da quando si carica l'entità.

    Usa il nome del registro delle entità e, se manca, l'identificativo
    scritto in modo leggibile. Non usa lo stato, che all'avvio può non esserci
    ancora e farebbe cambiare il nome da un riavvio all'altro.
    """
    entry = er.async_get(hass).async_get(entity_id)
    if entry is not None and (entry.name or entry.original_name):
        return entry.name or entry.original_name
    return entity_id.split(".", 1)[1].replace("_", " ").title()


class ValveEnableSwitch(SwitchEntity, RestoreEntity):
    """Abilita o esclude una singola valvola dal termostato."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:valve"

    def __init__(self, hass, entry: ConfigEntry, zone, heater: str) -> None:
        self._zone = zone
        self._heater = heater
        self._attr_translation_key = "valve_enabled"
        self._attr_translation_placeholders = {"valve": _valve_label(hass, heater)}
        self._attr_unique_id = f"{entry.entry_id}_{heater}_enabled"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
        )

    @property
    def is_on(self) -> bool:
        return self._zone.enabled.get(self._heater, True)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._zone.listeners.append(self._zone_changed)
        self.async_on_remove(lambda: self._zone.listeners.remove(self._zone_changed))
        last = await self.async_get_last_state()
        if last is not None and last.state in (STATE_ON, STATE_OFF):
            self._zone.enabled[self._heater] = last.state == STATE_ON
            self._zone.notify(self.hass)

    async def _zone_changed(self) -> None:
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._zone.enabled[self._heater] = True
        self.async_write_ha_state()
        self._zone.notify(self.hass)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._zone.enabled[self._heater] = False
        self.async_write_ha_state()
        self._zone.notify(self.hass)


class SlotDaySwitch(SwitchEntity):
    """Giorno della fascia che si sta componendo (editor da dashboard)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False
    _attr_icon = "mdi:calendar-check"

    def __init__(self, entry: ConfigEntry, zone, key: str) -> None:
        self._zone = zone
        self._key = key
        self._attr_translation_key = f"slot_day_{key}"
        self._attr_unique_id = f"{entry.entry_id}_slot_day_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
        )

    @property
    def is_on(self) -> bool:
        return self._key in self._zone.editor["days"]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._zone.editor_listeners.append(self._refresh)
        self.async_on_remove(lambda: self._zone.editor_listeners.remove(self._refresh))

    @callback
    def _refresh(self) -> None:
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self._key not in self._zone.editor["days"]:
            self._zone.editor["days"].append(self._key)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self._key in self._zone.editor["days"]:
            self._zone.editor["days"].remove(self._key)
        self.async_write_ha_state()
