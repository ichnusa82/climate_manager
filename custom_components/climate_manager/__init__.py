"""Climate Manager integration."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_BOILER_SETPOINT,
    CONF_SCHEDULE_SLOTS,
    DAY_ORDER,
    DOMAIN,
    HEAT_SOURCE_HEATING,
    get_heaters,
    get_shared_setpoint,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CARD_FILE = "climate-manager-schedule-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILE}"

PLATFORMS = [
    Platform.CLIMATE,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.TIME,
    Platform.BUTTON,
]


class ZoneData:
    """Stato condiviso tra termostato, valvole, fasce orarie e setpoint."""

    def __init__(self, heaters: list[str], slots: list[dict], entry: ConfigEntry) -> None:
        self.entry = entry
        self.enabled: dict[str, bool] = {h: True for h in heaters}
        self.heat_source: str = HEAT_SOURCE_HEATING  # heating, ac or both
        self.shared: dict | None = None  # setpoint caldaia unico (se configurato)
        self.listeners: list = []
        # fasce orarie e relativo editor da dashboard
        self.slots: list[dict] = [dict(s) for s in slots]
        self.editor: dict = {
            "days": ["mon", "tue", "wed", "thu", "fri"],
            "start": "06:30",
            "end": "08:30",
            "selected": None,
        }
        self.editor_listeners: list = []

    # ---------- notifiche ----------
    def notify(self, hass: HomeAssistant) -> None:
        for listener in list(self.listeners):
            hass.async_create_task(listener())

    def editor_changed(self) -> None:
        for listener in list(self.editor_listeners):
            listener()

    # ---------- fasce orarie ----------
    def set_slots(self, hass: HomeAssistant, slots: list[dict]) -> None:
        self.slots = [dict(s) for s in slots]
        selected = self.editor["selected"]
        if selected is not None and selected >= len(self.slots):
            self.editor["selected"] = None
        self.editor_changed()
        self.notify(hass)

    def persist(self, hass: HomeAssistant) -> None:
        hass.config_entries.async_update_entry(
            self.entry,
            options={
                **self.entry.options,
                CONF_SCHEDULE_SLOTS: [dict(s) for s in self.slots],
            },
        )
        self.editor_changed()
        self.notify(hass)

    def save_editor(self, hass: HomeAssistant) -> None:
        """Aggiunge una fascia nuova o aggiorna quella selezionata."""
        days = [d for d in DAY_ORDER if d in self.editor["days"]]
        if not days:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_day"
            )
        if self.editor["start"] == self.editor["end"]:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="same_time"
            )
        slot = {"days": days, "start": self.editor["start"], "end": self.editor["end"]}
        selected = self.editor["selected"]
        if selected is None or selected >= len(self.slots):
            self.slots.append(slot)
            self.editor["selected"] = len(self.slots) - 1
        else:
            self.slots[selected] = slot
        self.persist(hass)

    def delete_selected(self, hass: HomeAssistant) -> None:
        selected = self.editor["selected"]
        if selected is None or selected >= len(self.slots):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="select_slot_first"
            )
        del self.slots[selected]
        self.editor["selected"] = None
        self.persist(hass)

    def clear_all(self, hass: HomeAssistant) -> None:
        self.slots = []
        self.editor["selected"] = None
        self.persist(hass)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Registra la card cronotermostato: si carica da sola, senza aggiungere risorse."""
    try:
        from homeassistant.components.frontend import add_extra_js_url
        from homeassistant.components.http import StaticPathConfig

        manifest = json.loads((Path(__file__).parent / "manifest.json").read_text())
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(Path(__file__).parent / "frontend" / CARD_FILE), True)]
        )
        add_extra_js_url(hass, f"{CARD_URL}?v={manifest.get('version', '0')}")
    except Exception:  # noqa: BLE001 - la card è un extra, l'integrazione funziona lo stesso
        _LOGGER.warning("Impossibile registrare la card cronotermostato", exc_info=True)
    return True


def _options_signature(entry: ConfigEntry) -> str:
    """Impronta delle impostazioni, escluse le fasce orarie."""
    cfg = {**entry.data, **entry.options}
    cfg.pop(CONF_SCHEDULE_SLOTS, None)
    return json.dumps(cfg, sort_keys=True, default=str)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Crea il termostato da una config entry."""
    cfg = {**entry.data, **entry.options}
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data.setdefault("demand", {})
    zone = ZoneData(get_heaters(cfg), cfg.get(CONF_SCHEDULE_SLOTS) or [], entry)
    domain_data.setdefault("zones", {})[entry.entry_id] = zone
    domain_data.setdefault("opts_sig", {})[entry.entry_id] = _options_signature(entry)
    if cfg.get(CONF_BOILER_SETPOINT):
        zone.shared = get_shared_setpoint(hass, cfg[CONF_BOILER_SETPOINT])
        zone.shared["zones"].add(zone)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Rimuove il termostato."""
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        zone = hass.data[DOMAIN]["zones"].pop(entry.entry_id, None)
        hass.data[DOMAIN].get("opts_sig", {}).pop(entry.entry_id, None)
        if zone is not None and zone.shared is not None:
            zone.shared["zones"].discard(zone)
    return ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ricarica se cambiano le impostazioni; per le sole fasce aggiorna senza ricaricare."""
    zone = hass.data[DOMAIN]["zones"].get(entry.entry_id)
    same = hass.data[DOMAIN].get("opts_sig", {}).get(entry.entry_id) == _options_signature(entry)
    if zone is not None and same:
        zone.set_slots(hass, list(entry.options.get(CONF_SCHEDULE_SLOTS) or []))
        return
    await hass.config_entries.async_reload(entry.entry_id)
