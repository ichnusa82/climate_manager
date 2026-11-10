"""Heat source selector: heating, AC or both."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_AC,
    CONF_COOLING_ENABLED,
    CONF_INPUT_TYPE,
    INPUT_CONTACT,
    SEASON_SUMMER,
    SEASON_WINTER,
    DOMAIN,
    NEW_SLOT_LABEL,
    lang_of,
    slot_summary,
    HEAT_SOURCE_AC,
    HEAT_SOURCE_BOTH,
    HEAT_SOURCE_HEATING,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    cfg = {**entry.data, **entry.options}
    zone = hass.data[DOMAIN]["zones"][entry.entry_id]
    entities: list[SelectEntity] = [SlotSelect(entry, zone)]
    if cfg.get(CONF_AC):  # without an AC the heat comes only from the heating system
        entities.append(HeatSourceSelect(entry, zone))
    # solo per il cronotermostato a contatto (senza sonda) che può fare anche freddo
    if cfg.get(CONF_INPUT_TYPE) == INPUT_CONTACT and (
        cfg.get(CONF_AC) or cfg.get(CONF_COOLING_ENABLED)
    ):
        entities.append(SeasonSelect(entry, zone))
    async_add_entities(entities)


class HeatSourceSelect(SelectEntity, RestoreEntity):
    """Con quale sorgente fa caldo il termostato in modalità Heat/Auto."""

    _attr_has_entity_name = True
    _attr_translation_key = "heat_source"
    _attr_should_poll = False
    _attr_icon = "mdi:radiator"
    _attr_options = [HEAT_SOURCE_HEATING, HEAT_SOURCE_AC, HEAT_SOURCE_BOTH]

    def __init__(self, entry: ConfigEntry, zone) -> None:
        self._zone = zone
        self._attr_unique_id = f"{entry.entry_id}_heat_source"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
        )

    @property
    def current_option(self) -> str:
        return self._zone.heat_source

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in self._attr_options:
            self._zone.heat_source = last.state
            self._zone.notify(self.hass)

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            return
        self._zone.heat_source = option
        self.async_write_ha_state()
        self._zone.notify(self.hass)


class SlotSelect(SelectEntity):
    """Sceglie quale fascia modificare (o "Nuova fascia") nell'editor da dashboard."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "slot"
    _attr_should_poll = False
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, entry: ConfigEntry, zone) -> None:
        self._zone = zone
        self._attr_unique_id = f"{entry.entry_id}_slot_select"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
        )

    @property
    def _lang(self) -> str:
        return lang_of(self.hass.config.language)

    @property
    def _new_label(self) -> str:
        return NEW_SLOT_LABEL[self._lang]

    def _label(self, index: int) -> str:
        return f"{index + 1}: {slot_summary(self._zone.slots[index], self._lang)}"

    @property
    def options(self) -> list[str]:
        return [self._new_label] + [self._label(i) for i in range(len(self._zone.slots))]

    @property
    def current_option(self) -> str:
        selected = self._zone.editor["selected"]
        if selected is None or selected >= len(self._zone.slots):
            return self._new_label
        return self._label(selected)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._zone.editor_listeners.append(self._refresh)
        self.async_on_remove(lambda: self._zone.editor_listeners.remove(self._refresh))

    @callback
    def _refresh(self) -> None:
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        editor = self._zone.editor
        if option == self._new_label:
            editor["selected"] = None
        else:
            index = int(option.split(":")[0]) - 1
            if not 0 <= index < len(self._zone.slots):
                return
            slot = self._zone.slots[index]
            editor["selected"] = index
            editor["days"] = list(slot["days"])
            editor["start"] = slot["start"]
            editor["end"] = slot["end"]
        self._zone.editor_changed()


class SeasonSelect(SelectEntity, RestoreEntity):
    """Stagione del programma Auto: Inverno scalda, Estate raffresca."""

    _attr_has_entity_name = True
    _attr_translation_key = "season"
    _attr_should_poll = False
    _attr_options = [SEASON_WINTER, SEASON_SUMMER]

    def __init__(self, entry: ConfigEntry, zone) -> None:
        self._zone = zone
        self._attr_unique_id = f"{entry.entry_id}_season"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
        )

    @property
    def icon(self) -> str:
        return "mdi:white-balance-sunny" if self._zone.season == SEASON_SUMMER else "mdi:snowflake"

    @property
    def current_option(self) -> str:
        return self._zone.season

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._zone.listeners.append(self._zone_changed)
        self.async_on_remove(lambda: self._zone.listeners.remove(self._zone_changed))
        last = await self.async_get_last_state()
        if last is not None and last.state in self._attr_options:
            self._zone.season = last.state
            self._zone.notify(self.hass)

    async def _zone_changed(self) -> None:
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options or option == self._zone.season:
            return
        self._zone.season = option
        self.async_write_ha_state()
        self._zone.notify(self.hass)
