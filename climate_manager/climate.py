"""Thermostat entity of Climate Manager."""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    BLOCK_ECO,
    BLOCK_OFF,
    CONF_BLOCK_CALENDARS,
    CONF_BLOCK_MODE,
    CONF_AC,
    HEAT_SOURCE_AC,
    HEAT_SOURCE_BOTH,
    CONF_ANTIFREEZE,
    ANTIFREEZE_MARGIN,
    DEFAULT_ANTIFREEZE,
    CONF_BOILER,
    CONF_WINDOW_DELAY,
    CONF_WINDOWS,
    DEFAULT_WINDOW_DELAY,
    CONF_CONTACT,
    CONF_CONTACT_INVERT,
    CONF_INPUT_TYPE,
    INPUT_CONTACT,
    INPUT_TEMPERATURE,
    CONF_COLD_TOLERANCE,
    CONF_COOLING_ENABLED,
    CONF_HOT_TOLERANCE,
    CONF_MIN_CYCLE,
    DEFAULT_COOL_TARGET,
    CONF_PUMP,
    CONF_COMFORT_TEMP,
    CONF_ECO_TEMP,
    CONF_SCHEDULE_SLOTS,
    DEFAULT_COMFORT_TEMP,
    DEFAULT_ECO_TEMP,
    CONF_BOILER_SETPOINT,
    CONF_OVERRIDE_ENTITY,
    CONF_OVERRIDE_VALUE,
    DEFAULT_OVERRIDE_VALUE,
    CONF_HYSTERESIS,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_PRESET_ORDER,
    CONF_PRESETS,
    CONF_SENSOR,
    DEFAULT_HYSTERESIS,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_TARGET_TEMP,
    DOMAIN,
    get_heaters,
    parse_slots,
    slot_active,
    sort_by_order,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    zone = hass.data[DOMAIN]["zones"][entry.entry_id]
    async_add_entities([ClimateManagerThermostat(entry, zone)])


class ClimateManagerThermostat(ClimateEntity, RestoreEntity):
    """Termostato con isteresi che comanda uno o più relè/elettrovalvole."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "thermostat"
    _attr_should_poll = False
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, entry: ConfigEntry, zone) -> None:
        cfg = {**entry.data, **entry.options}
        self._zone = zone
        self._sensor: str | None = cfg.get(CONF_SENSOR) or None
        self._heaters = get_heaters(cfg)
        self._boiler: str | None = cfg.get(CONF_BOILER) or None
        self._pump: str | None = cfg.get(CONF_PUMP) or None
        self._boiler_sp: str | None = cfg.get(CONF_BOILER_SETPOINT) or None
        self._override: str | None = cfg.get(CONF_OVERRIDE_ENTITY) or None
        self._override_value = float(
            cfg.get(CONF_OVERRIDE_VALUE, DEFAULT_OVERRIDE_VALUE)
        )

        # preset: ognuno è un insieme di valvole da tenere attive
        self._presets: dict[str, list[str]] = {}
        if len(self._heaters) > 1:
            for name, valves in (cfg.get(CONF_PRESETS) or {}).items():
                valid = [v for v in valves if v in self._heaters]
                if valid:
                    self._presets[name] = valid
            self._presets = {
                n: self._presets[n]
                for n in sort_by_order(
                    list(self._presets), cfg.get(CONF_PRESET_ORDER)
                )
            }
            if self._presets:
                self._attr_preset_modes = list(self._presets)
                self._attr_supported_features = (
                    self._attr_supported_features | ClimateEntityFeature.PRESET_MODE
                )
        self._calling = False
        fallback = float(cfg.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS))
        self._hot_tol = float(cfg.get(CONF_HOT_TOLERANCE, fallback))
        self._cold_tol = float(cfg.get(CONF_COLD_TOLERANCE, fallback))
        self._min_cycle = float(cfg.get(CONF_MIN_CYCLE, 0)) * 60.0  # in secondi
        self._ac: str | None = cfg.get(CONF_AC) or None
        self._ac_commanded = False  # True se il climatizzatore l'abbiamo acceso noi
        # con un climatizzatore la modalità freddo è sempre disponibile
        self._cooling = bool(cfg.get(CONF_COOLING_ENABLED, False)) or bool(self._ac)
        self._cool_target = DEFAULT_COOL_TARGET
        self._last_change: float | None = None
        self._antifreeze = float(cfg.get(CONF_ANTIFREEZE, DEFAULT_ANTIFREEZE))
        self._antifreeze_active = False
        self._attr_min_temp = float(cfg.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP))
        self._attr_max_temp = float(cfg.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP))
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
        )
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_native_target_temperature = DEFAULT_TARGET_TEMP
        self._attr_native_current_temperature: float | None = None

        # cronotermostato: programma orario (helper "Programma")
        self._last_on: bool | None = None
        # calendari di blocco: se uno è attivo il programma Auto è bloccato
        self._block_cals = list(cfg.get(CONF_BLOCK_CALENDARS) or [])
        self._block_mode = cfg.get(CONF_BLOCK_MODE, BLOCK_OFF)
        # finestre/porte: se una resta aperta oltre il ritardo, il riscaldamento si sospende
        self._windows = list(cfg.get(CONF_WINDOWS) or [])
        self._window_delay = float(cfg.get(CONF_WINDOW_DELAY, DEFAULT_WINDOW_DELAY)) * 60.0
        self._window_open_since: float | None = None
        self._comfort = float(cfg.get(CONF_COMFORT_TEMP, DEFAULT_COMFORT_TEMP))
        self._eco = float(cfg.get(CONF_ECO_TEMP, DEFAULT_ECO_TEMP))
        self._manual_target = DEFAULT_TARGET_TEMP
        self._temp_override: float | None = None
        modes = [HVACMode.HEAT]
        if self._cooling:
            modes.append(HVACMode.COOL)
        if self._slots:
            modes.append(HVACMode.AUTO)
        modes.append(HVACMode.OFF)
        self._attr_hvac_modes = modes

        # ingresso: sensore di temperatura oppure contatto di un termostato fisico
        self._input_type = cfg.get(CONF_INPUT_TYPE, INPUT_TEMPERATURE)
        self._contact_mode = self._input_type == INPUT_CONTACT
        self._contact: str | None = cfg.get(CONF_CONTACT) or None
        self._contact_invert = bool(cfg.get(CONF_CONTACT_INVERT, False))
        if self._contact_mode:
            # decide il termostato fisico: niente temperatura e tolleranze; restano
            # modi (caldo/freddo), sorgenti (radiante/climatizzatore) e fasce
            modes = [HVACMode.HEAT]
            if self._cooling:
                modes.append(HVACMode.COOL)
            if self._slots:
                modes.append(HVACMode.AUTO)
            modes.append(HVACMode.OFF)
            self._attr_hvac_modes = modes
            self._attr_supported_features = (
                self._attr_supported_features & ~ClimateEntityFeature.TARGET_TEMPERATURE
            )

    # ---------- ciclo di vita ----------
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        if (last := await self.async_get_last_state()) is not None:
            if last.state in [m.value for m in self.hvac_modes]:
                self._attr_hvac_mode = HVACMode(last.state)
            if (m := last.attributes.get("manual_temperature")) is not None:
                self._manual_target = float(m)
            elif (
                t := last.attributes.get(ATTR_TEMPERATURE)
            ) is not None and last.state not in (HVACMode.AUTO, HVACMode.COOL):
                self._manual_target = float(t)
            if (c := last.attributes.get("cool_temperature")) is not None:
                self._cool_target = float(c)

        if self._contact_mode:
            if self._contact:
                self.async_on_remove(
                    async_track_state_change_event(
                        self.hass, [self._contact], self._contact_changed
                    )
                )
        elif self._sensor:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._sensor], self._sensor_changed
                )
            )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._heaters, self._heater_changed
            )
        )

        if self._windows:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, self._windows, self._window_changed
                )
            )
        if self._block_cals:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, self._block_cals, self._block_changed
                )
            )
        if self._override:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._override], self._override_changed
                )
            )
        # riapplica lo stato giusto ogni minuto (utile dopo un blackout)
        self.async_on_remove(
            async_track_time_interval(self.hass, self._periodic, timedelta(minutes=1))
        )

        # richiamato quando si abilita/esclude una valvola
        self._zone.listeners.append(self._zone_changed)
        self.async_on_remove(lambda: self._zone.listeners.remove(self._zone_changed))

        self._calling = any(self._is_on(h) for h in self._active_heaters())
        if self._sensor and not self._contact_mode:
            self._update_current_temp(self.hass.states.get(self._sensor))
        await self._async_control()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        self._calling = False
        await self._async_boiler()
        await self._async_pump()
        await self._async_ac(False)

    # ---------- proprietà ----------
    @property
    def _slots(self):
        """Fasce orarie attuali (modificabili anche da dashboard)."""
        return parse_slots(self._zone.slots)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        modes = [HVACMode.HEAT]
        if self._cooling:
            modes.append(HVACMode.COOL)
        if self._slots:
            modes.append(HVACMode.AUTO)
        modes.append(HVACMode.OFF)
        return modes

    @property
    def hvac_action(self) -> HVACAction:
        if self._antifreeze_active:
            return HVACAction.HEATING
        if self._attr_hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        active = (
            self._calling
            if self._use_ac()
            else any(self._is_on(h) for h in self._active_heaters())
        )
        if active:
            if self._attr_hvac_mode == HVACMode.COOL:
                return HVACAction.COOLING
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        if not self._presets:
            return None
        active = set(self._active_heaters())
        for name, valves in self._presets.items():
            if set(valves) == active:
                return name
        return None  # nessun preset corrisponde alle valvole attive

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "active_valves": self._active_heaters(),
            "manual_temperature": self._manual_target,
        }
        if self._antifreeze > 0:
            attrs["antifreeze_active"] = self._antifreeze_active
        if self._windows:
            attrs["window_open"] = self._windows_open()
            attrs["window_suspended"] = (
                self._windows_open()
                and self._window_open_since is not None
                and time.monotonic() - self._window_open_since >= self._window_delay
            )
        if self._contact_mode:
            attrs["contact_request"] = self._contact_on()
        if self._cooling:
            attrs["cool_temperature"] = self._cool_target
        if self._ac:
            if self._use_ac() and self._use_heating():
                attrs["active_source"] = "heating + ac"
            elif self._use_ac():
                attrs["active_source"] = "ac"
            else:
                attrs["active_source"] = "heating"
        if self._block_cals:
            attrs["blocked"] = self._blocked()
        if self._slots and self._contact_mode:
            attrs["schedule_state"] = "in_slot" if self._schedule_on() else "outside_slot"
        elif self._slots:
            attrs.update(
                {
                    "comfort_temperature": self._comfort,
                    "eco_temperature": self._eco,
                    "schedule_state": "comfort" if self._schedule_on() else "eco",
                    "temporary_override": self._temp_override,
                }
            )
        return attrs

    # ---------- comandi da HA ----------
    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        if self._attr_hvac_mode == HVACMode.AUTO and self._slots:
            # in automatico vale fino al prossimo cambio di fascia
            self._temp_override = float(temp)
        elif self._attr_hvac_mode == HVACMode.COOL:
            self._cool_target = float(temp)
        else:
            self._manual_target = float(temp)
        await self._async_control()
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode not in self.hvac_modes:
            return
        old_mode = self._attr_hvac_mode
        self._attr_hvac_mode = hvac_mode
        self._temp_override = None
        self._last_change = None  # un cambio di modo non è vincolato dal ciclo minimo
        if HVACMode.COOL in (old_mode, hvac_mode):
            self._calling = False
        await self._async_control()
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in self._presets:
            return
        valves = self._presets[preset_mode]
        for heater in self._heaters:
            self._zone.enabled[heater] = heater in valves
        self._zone.notify(self.hass)

    # ---------- eventi ----------
    @callback
    def _sensor_changed(self, event: Event) -> None:
        self._update_current_temp(event.data.get("new_state"))
        self.hass.async_create_task(self._async_control())
        self.async_write_ha_state()

    @callback
    def _heater_changed(self, event: Event) -> None:
        self.async_write_ha_state()

    @callback
    def _contact_changed(self, event: Event) -> None:
        self.hass.async_create_task(self._async_control())
        self.async_write_ha_state()

    @callback
    def _window_changed(self, event: Event) -> None:
        self.hass.async_create_task(self._async_control())
        self.async_write_ha_state()

    @callback
    def _block_changed(self, event: Event) -> None:
        self._temp_override = None  # una modifica temporanea non sopravvive al blocco
        self.hass.async_create_task(self._async_control())
        self.async_write_ha_state()

    @callback
    def _override_changed(self, event: Event) -> None:
        self.hass.async_create_task(self._async_control())

    async def _periodic(self, now) -> None:
        await self._async_control()
        self.async_write_ha_state()

    async def _zone_changed(self) -> None:
        await self._async_control()
        self.async_write_ha_state()

    def _update_current_temp(self, state) -> None:
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._attr_native_current_temperature = None
            return
        try:
            self._attr_native_current_temperature = float(state.state)
        except ValueError:
            _LOGGER.warning("Valore non numerico da %s: %s", self._sensor, state.state)
            self._attr_native_current_temperature = None

    # ---------- logica ----------
    def _windows_open(self) -> bool:
        """True se almeno una finestra/porta è aperta in questo momento."""
        return any(self._is_on(w) for w in self._windows)

    def _window_suspended(self) -> bool:
        """True se una finestra è aperta da più del ritardo impostato."""
        if not self._windows:
            return False
        if not self._windows_open():
            self._window_open_since = None
            return False
        now = time.monotonic()
        if self._window_open_since is None:
            self._window_open_since = now
        return now - self._window_open_since >= self._window_delay

    def _contact_on(self) -> bool:
        """True se il termostato fisico chiede calore."""
        state = self.hass.states.get(self._contact) if self._contact else None
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return False
        closed = state.state == STATE_ON
        return (not closed) if self._contact_invert else closed

    def _blocked(self) -> bool:
        """True se almeno un calendario di blocco ha un evento in corso."""
        return any(self._is_on(c) for c in self._block_cals)

    def _schedule_on(self) -> bool:
        """True se adesso siamo dentro una fascia comfort."""
        now = dt_util.now()
        return slot_active(self._slots, now.weekday(), now.hour * 60 + now.minute)

    def _recompute_target(self) -> None:
        """Calcola la temperatura obiettivo in base a modo e programma."""
        on = self._schedule_on()
        if self._last_on is not None and on != self._last_on:
            self._temp_override = None  # nuova fascia: finisce la modifica temporanea
        self._last_on = on
        if self._attr_hvac_mode == HVACMode.AUTO and self._slots:
            if self._blocked() and self._block_mode == BLOCK_ECO:
                target = self._eco
            elif self._temp_override is not None:
                target = self._temp_override
            else:
                target = self._comfort if self._schedule_on() else self._eco
        elif self._attr_hvac_mode == HVACMode.COOL:
            target = self._cool_target
        else:
            target = self._manual_target
        self._attr_native_target_temperature = target

    def _is_on(self, entity_id: str) -> bool:
        state = self.hass.states.get(entity_id)
        return state is not None and state.state == STATE_ON

    def _active_heaters(self) -> list[str]:
        """Valvole abilitate (le altre vengono sempre tenute chiuse)."""
        return [h for h in self._heaters if self._zone.enabled.get(h, True)]

    async def _async_heaters(self, turn_on: bool, force_all: bool = False) -> None:
        for heater in self._heaters:
            want = turn_on and (force_all or self._zone.enabled.get(heater, True))
            if want != self._is_on(heater):
                await self.hass.services.async_call(
                    "homeassistant",
                    SERVICE_TURN_ON if want else SERVICE_TURN_OFF,
                    {ATTR_ENTITY_ID: heater},
                    blocking=False,
                )

    async def _async_follow_demand(self, entity_id: str | None, active: bool) -> None:
        """Accende l'entità se almeno un termostato richiede calore, altrimenti la spegne."""
        if not entity_id:
            return
        demand = self.hass.data[DOMAIN]["demand"].setdefault(entity_id, set())
        if active:
            demand.add(self.entity_id)
        else:
            demand.discard(self.entity_id)

        want = bool(demand)
        if want != self._is_on(entity_id):
            await self.hass.services.async_call(
                "homeassistant",
                SERVICE_TURN_ON if want else SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: entity_id},
                blocking=False,
            )

    async def _async_boiler(self) -> None:
        """Comando caldaia: solo per richiesta di calore, mai in modalità freddo."""
        await self._async_follow_demand(
            self._boiler,
            self._calling
            and self._use_heating()
            and (self._attr_hvac_mode != HVACMode.COOL or self._antifreeze_active),
        )

    async def _async_pump(self) -> None:
        """Comando pompa: per qualsiasi richiesta, caldo o freddo."""
        await self._async_follow_demand(self._pump, self._calling and self._use_heating())

    async def _async_boiler_setpoint(self) -> None:
        """Scrive sulla caldaia il setpoint unico (o quello di override)."""
        shared = self._zone.shared
        if not self._boiler_sp or shared is None or not shared["ready"]:
            return

        if self._override and self._is_on(self._override):
            value = self._override_value
        else:
            value = shared["value"]

        state = self.hass.states.get(self._boiler_sp)
        try:
            current = float(state.state) if state is not None else None
        except ValueError:
            current = None
        if current is None or abs(current - value) > 0.01:
            await self.hass.services.async_call(
                self._boiler_sp.split(".")[0],  # number / input_number
                "set_value",
                {ATTR_ENTITY_ID: self._boiler_sp, "value": value},
                blocking=False,
            )

    def _use_ac(self) -> bool:
        """True se in questo momento la sorgente è il climatizzatore."""
        if self._antifreeze_active or not self._ac:
            return False
        if self._attr_hvac_mode == HVACMode.COOL:
            return True  # il freddo si fa sempre con il climatizzatore
        if self._attr_hvac_mode in (HVACMode.HEAT, HVACMode.AUTO):
            return self._zone.heat_source in (HEAT_SOURCE_AC, HEAT_SOURCE_BOTH)
        return False

    def _use_heating(self) -> bool:
        """True se in questo momento lavora l'heating system (valves, pump, boiler)."""
        if not self._use_ac():
            return True
        # caldo combinato: radiante e climatizzatore insieme
        return (
            self._attr_hvac_mode in (HVACMode.HEAT, HVACMode.AUTO)
            and self._zone.heat_source == HEAT_SOURCE_BOTH
        )

    async def _async_ac(self, use_ac: bool) -> None:
        """Comanda il climatizzatore (entità climate, switch o input_boolean)."""
        if not self._ac:
            return
        state = self.hass.states.get(self._ac)
        if state is None or state.state == STATE_UNAVAILABLE:
            return
        domain = self._ac.split(".")[0]

        if use_ac and self._calling:
            self._ac_commanded = True
            if domain == "climate":
                mode = "cool" if self._attr_hvac_mode == HVACMode.COOL else "heat"
                if state.state != mode:
                    await self.hass.services.async_call(
                        "climate",
                        "set_hvac_mode",
                        {ATTR_ENTITY_ID: self._ac, "hvac_mode": mode},
                        blocking=False,
                    )
                if self._contact_mode:
                    return  # senza temperatura obiettivo: solo acceso/spento
                target = self._attr_native_target_temperature
                try:
                    current = float(state.attributes.get("temperature"))
                except (TypeError, ValueError):
                    current = None
                if current is None or abs(current - target) > 0.01:
                    await self.hass.services.async_call(
                        "climate",
                        "set_temperature",
                        {ATTR_ENTITY_ID: self._ac, "temperature": target},
                        blocking=False,
                    )
            elif state.state != STATE_ON:
                await self.hass.services.async_call(
                    "homeassistant",
                    SERVICE_TURN_ON,
                    {ATTR_ENTITY_ID: self._ac},
                    blocking=False,
                )
        elif use_ac or self._ac_commanded:
            # lo spegniamo solo se è la sorgente attiva o se l'avevamo acceso noi,
            # così non interferiamo con un uso manuale del climatizzatore
            self._ac_commanded = False
            if domain == "climate":
                if state.state != "off":
                    await self.hass.services.async_call(
                        "climate",
                        "set_hvac_mode",
                        {ATTR_ENTITY_ID: self._ac, "hvac_mode": "off"},
                        blocking=False,
                    )
            elif state.state == STATE_ON:
                await self.hass.services.async_call(
                    "homeassistant",
                    SERVICE_TURN_OFF,
                    {ATTR_ENTITY_ID: self._ac},
                    blocking=False,
                )

    def _update_antifreeze(self, cur: float | None) -> bool:
        """Antigelo: sotto la soglia scalda sempre, anche da spento (serve il sensore)."""
        if self._antifreeze <= 0 or self._contact_mode or cur is None:
            self._antifreeze_active = False
        elif cur <= self._antifreeze:
            self._antifreeze_active = True
        elif cur >= self._antifreeze + ANTIFREEZE_MARGIN:
            self._antifreeze_active = False
        return self._antifreeze_active

    def _set_calling(self, value: bool) -> None:
        if value != self._calling:
            self._calling = value
            self._last_change = time.monotonic()

    def _cycle_elapsed(self) -> bool:
        """True se è passato il ciclo minimo dall'ultimo cambio di stato."""
        if self._min_cycle <= 0 or self._last_change is None:
            return True
        return time.monotonic() - self._last_change >= self._min_cycle

    async def _async_control(self) -> None:
        """Regola le valvole (con tolleranze o dal contatto) e aggiorna caldaia e pompa."""
        if self._attr_hvac_mode == HVACMode.AUTO and not self._slots:
            self._attr_hvac_mode = HVACMode.HEAT  # senza fasce non c'è programma
        self._recompute_target()
        cur = self._attr_native_current_temperature
        cooling_mode = self._attr_hvac_mode == HVACMode.COOL
        antifreeze = self._update_antifreeze(cur)

        if antifreeze:
            # protezione antigelo: ha la precedenza su spento, blocco e finestra
            self._set_calling(True)
        else:
            forced_off = (
                self._attr_hvac_mode == HVACMode.OFF
                or (not self._contact_mode and cur is None)
                or (not self._active_heaters() and not self._use_ac())
                or (
                    self._attr_hvac_mode == HVACMode.AUTO
                    and self._blocked()
                    and self._block_mode == BLOCK_OFF
                )
                or (self._contact_mode and self._blocked())
                or self._window_suspended()
            )
            if forced_off:
                # spento, sensore non disponibile, nessuna valvola, blocco o finestra:
                # si ferma subito, senza aspettare il ciclo minimo
                self._set_calling(False)
            else:
                if self._contact_mode:
                    # in Auto il contatto vale solo dentro le fasce orarie
                    want = self._contact_on() and (
                        self._attr_hvac_mode != HVACMode.AUTO or self._schedule_on()
                    )
                else:
                    target = self._attr_native_target_temperature
                    want = self._calling
                    if cooling_mode:
                        if cur >= target + self._hot_tol:
                            want = True
                        elif cur <= target - self._cold_tol:
                            want = False
                    else:
                        if cur <= target - self._cold_tol:
                            want = True
                        elif cur >= target + self._hot_tol:
                            want = False
                if want != self._calling and self._cycle_elapsed():
                    self._set_calling(want)

        use_ac = self._use_ac()
        await self._async_heaters(
            self._calling and self._use_heating(), force_all=antifreeze
        )
        await self._async_boiler()
        await self._async_pump()
        await self._async_ac(use_ac)
        await self._async_boiler_setpoint()
