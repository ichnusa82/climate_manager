"""Config flow for Climate Manager."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    BLOCK_ECO,
    BLOCK_OFF,
    CONF_BLOCK_CALENDARS,
    CONF_BLOCK_MODE,
    CONF_AC,
    CONF_ANTIFREEZE,
    CONF_BOILER,
    DEFAULT_ANTIFREEZE,
    CONF_WINDOW_DELAY,
    CONF_WINDOWS,
    DEFAULT_WINDOW_DELAY,
    CONF_CONTACT,
    CONF_CONTACT_INVERT,
    CONF_INPUT_TYPE,
    INPUT_CONTACT,
    INPUT_TEMPERATURE,
    CONF_COLD_TOLERANCE,
    CONF_HOT_TOLERANCE,
    CONF_MIN_CYCLE,
    CONF_PUMP,
    CONF_COMFORT_TEMP,
    CONF_ECO_TEMP,
    CONF_COOL_COMFORT_TEMP,
    CONF_COOL_ECO_TEMP,
    DEFAULT_COOL_COMFORT_TEMP,
    DEFAULT_COOL_ECO_TEMP,
    CONF_SCHEDULE_SLOTS,
    DEFAULT_COMFORT_TEMP,
    DEFAULT_ECO_TEMP,
    CONF_BOILER_SETPOINT,
    CONF_OVERRIDE_ENTITY,
    CONF_OVERRIDE_VALUE,
    DEFAULT_OVERRIDE_VALUE,
    CONF_HEATER,
    CONF_HYSTERESIS,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_PRESET_ORDER,
    CONF_PRESETS,
    CONF_SENSOR,
    DEFAULT_HYSTERESIS,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN,
    NO_SLOTS_LABEL,
    get_heaters,
    lang_of,
    slot_summary,
    sort_by_order,
)

HEATER_DOMAINS = ["switch", "input_boolean"]
RESERVED_PRESET_NAMES = ("none", "nessuno")

DAY_OPTIONS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _days_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=DAY_OPTIONS,
            multiple=True,
            mode=selector.SelectSelectorMode.LIST,
            translation_key="days",
        )
    )


def _slot_summary(slot: dict[str, Any], language: str | None) -> str:
    return slot_summary(slot, language)


def _schedule_summary(slots: list[dict[str, Any]] | None, language: str | None) -> str:
    if not slots:
        return NO_SLOTS_LABEL[lang_of(language)]
    return "\n".join(f"• {slot_summary(s, language)}" for s in slots)


def _number(min_v: float, max_v: float, step: float) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_v, max=max_v, step=step, mode=selector.NumberSelectorMode.BOX
        )
    )


def _heater_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=HEATER_DOMAINS, multiple=True)
    )


def _validate_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Controlla che sia stato scelto l'ingresso giusto per il tipo selezionato."""
    errors: dict[str, str] = {}
    if user_input.get(CONF_INPUT_TYPE, INPUT_TEMPERATURE) == INPUT_CONTACT:
        if not user_input.get(CONF_CONTACT):
            errors[CONF_CONTACT] = "contact_required"
    elif not user_input.get(CONF_SENSOR):
        errors[CONF_SENSOR] = "sensor_required"
    return errors


_OPTIONAL_KEYS = (
    CONF_SENSOR,
    CONF_CONTACT,
    CONF_BOILER,
    CONF_PUMP,
    CONF_AC,
    CONF_BOILER_SETPOINT,
    CONF_OVERRIDE_ENTITY,
)


def _common_fields(defaults: dict[str, Any]) -> dict:
    return {
        vol.Required(
            CONF_INPUT_TYPE, default=defaults.get(CONF_INPUT_TYPE, INPUT_TEMPERATURE)
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[INPUT_TEMPERATURE, INPUT_CONTACT],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="input_type",
            )
        ),
        vol.Optional(
            CONF_SENSOR, description={"suggested_value": defaults.get(CONF_SENSOR)}
        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Optional(
            CONF_CONTACT, description={"suggested_value": defaults.get(CONF_CONTACT)}
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=["binary_sensor", "switch", "input_boolean"]
            )
        ),
        vol.Required(
            CONF_CONTACT_INVERT, default=defaults.get(CONF_CONTACT_INVERT, False)
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_BOILER, description={"suggested_value": defaults.get(CONF_BOILER)}
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=HEATER_DOMAINS)
        ),
        vol.Optional(
            CONF_PUMP, description={"suggested_value": defaults.get(CONF_PUMP)}
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=HEATER_DOMAINS)
        ),
        vol.Optional(
            CONF_AC, description={"suggested_value": defaults.get(CONF_AC)}
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["climate", *HEATER_DOMAINS])
        ),
        vol.Optional(
            CONF_BOILER_SETPOINT,
            description={"suggested_value": defaults.get(CONF_BOILER_SETPOINT)},
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["number", "input_number"])
        ),
        vol.Optional(
            CONF_OVERRIDE_ENTITY,
            description={"suggested_value": defaults.get(CONF_OVERRIDE_ENTITY)},
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=["switch", "input_boolean", "binary_sensor"]
            )
        ),
        vol.Required(
            CONF_OVERRIDE_VALUE,
            default=defaults.get(CONF_OVERRIDE_VALUE, DEFAULT_OVERRIDE_VALUE),
        ): _number(28, 70, 1),
        vol.Required(
            CONF_COMFORT_TEMP,
            default=defaults.get(CONF_COMFORT_TEMP, DEFAULT_COMFORT_TEMP),
        ): _number(0, 40, 0.5),
        vol.Required(
            CONF_ECO_TEMP, default=defaults.get(CONF_ECO_TEMP, DEFAULT_ECO_TEMP)
        ): _number(0, 40, 0.5),
        vol.Required(
            CONF_COOL_COMFORT_TEMP,
            default=defaults.get(CONF_COOL_COMFORT_TEMP, DEFAULT_COOL_COMFORT_TEMP),
        ): _number(0, 40, 0.5),
        vol.Required(
            CONF_COOL_ECO_TEMP,
            default=defaults.get(CONF_COOL_ECO_TEMP, DEFAULT_COOL_ECO_TEMP),
        ): _number(0, 40, 0.5),
        vol.Optional(
            CONF_BLOCK_CALENDARS,
            description={"suggested_value": defaults.get(CONF_BLOCK_CALENDARS)},
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="calendar", multiple=True)
        ),
        vol.Required(
            CONF_BLOCK_MODE, default=defaults.get(CONF_BLOCK_MODE, BLOCK_OFF)
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[BLOCK_OFF, BLOCK_ECO],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="block_mode",
            )
        ),
        vol.Optional(
            CONF_WINDOWS, description={"suggested_value": defaults.get(CONF_WINDOWS)}
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
        ),
        vol.Required(
            CONF_WINDOW_DELAY,
            default=defaults.get(CONF_WINDOW_DELAY, DEFAULT_WINDOW_DELAY),
        ): _number(0, 60, 1),
        vol.Required(
            CONF_ANTIFREEZE, default=defaults.get(CONF_ANTIFREEZE, DEFAULT_ANTIFREEZE)
        ): _number(0, 15, 0.5),
        vol.Required(
            CONF_HOT_TOLERANCE,
            default=defaults.get(
                CONF_HOT_TOLERANCE, defaults.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
            ),
        ): _number(0, 5, 0.1),
        vol.Required(
            CONF_COLD_TOLERANCE,
            default=defaults.get(
                CONF_COLD_TOLERANCE, defaults.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
            ),
        ): _number(0, 5, 0.1),
        vol.Required(
            CONF_MIN_CYCLE, default=defaults.get(CONF_MIN_CYCLE, 0)
        ): _number(0, 120, 1),
        vol.Required(
            CONF_MIN_TEMP, default=defaults.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP)
        ): _number(0, 40, 0.5),
        vol.Required(
            CONF_MAX_TEMP, default=defaults.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP)
        ): _number(0, 40, 0.5),
    }


class ClimateManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Crea un termostato dall'interfaccia."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_input(user_input)
            if not errors:
                await self.async_set_unique_id(user_input[CONF_NAME].strip().lower())
                self._abort_if_unique_id_configured()
                for key in _OPTIONAL_KEYS:
                    user_input.setdefault(key, None)
                user_input.setdefault(CONF_BLOCK_CALENDARS, [])
                user_input.setdefault(CONF_WINDOWS, [])
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Required(CONF_HEATER): _heater_selector(),
                **_common_fields({}),
            }
        )
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return ClimateManagerOptionsFlow()


class ClimateManagerOptionsFlow(OptionsFlow):
    """Impostazioni, valvole e preset."""

    _edit_name: str = ""
    _edit_slot: int = 0

    def _current(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        current = self._current()
        menu = ["settings"]
        if len(get_heaters(current)) > 1:
            menu.append("add_preset")
            if current.get(CONF_PRESETS):
                menu.append("edit_preset")
                if len(current.get(CONF_PRESETS) or {}) > 1:
                    menu.append("sort_presets")
                menu.append("delete_preset")
        menu.append("add_slot")
        if current.get(CONF_SCHEDULE_SLOTS):
            menu += ["edit_slot", "delete_slot"]
        return self.async_show_menu(
            step_id="init",
            menu_options=menu,
            description_placeholders={
                "schedule": _schedule_summary(
                    current.get(CONF_SCHEDULE_SLOTS), self.hass.config.language
                )
            },
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        current = self._current()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_input(user_input)
            if not errors:
                for key in _OPTIONAL_KEYS:
                    user_input.setdefault(key, None)
                user_input.setdefault(CONF_BLOCK_CALENDARS, [])
                user_input.setdefault(CONF_WINDOWS, [])
                return self.async_create_entry(
                    data={**self.config_entry.options, **user_input}
                )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HEATER, description={"suggested_value": get_heaters(current)}
                ): _heater_selector(),
                **_common_fields(current),
            }
        )
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(
            step_id="settings", data_schema=schema, errors=errors
        )

    async def async_step_add_preset(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        current = self._current()
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input["name"].strip()
            if not name or name.lower() in RESERVED_PRESET_NAMES:
                errors["name"] = "reserved_name"
            elif not user_input["valves"]:
                errors["valves"] = "no_valve"
            else:
                presets = dict(current.get(CONF_PRESETS) or {})
                presets[name] = list(user_input["valves"])
                return self.async_create_entry(
                    data={**self.config_entry.options, CONF_PRESETS: presets}
                )
        schema = vol.Schema(
            {
                vol.Required("name"): selector.TextSelector(),
                vol.Required("valves"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        include_entities=get_heaters(current), multiple=True
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="add_preset", data_schema=schema, errors=errors
        )

    async def async_step_edit_preset(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        presets = dict(self._current().get(CONF_PRESETS) or {})
        if not presets:
            return self.async_abort(reason="no_presets")
        if user_input is not None:
            self._edit_name = user_input["preset"]
            return await self.async_step_edit_preset_details()
        schema = vol.Schema(
            {
                vol.Required("preset"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=list(presets))
                )
            }
        )
        return self.async_show_form(step_id="edit_preset", data_schema=schema)

    async def async_step_edit_preset_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        current = self._current()
        heaters = get_heaters(current)
        presets = dict(current.get(CONF_PRESETS) or {})
        old = self._edit_name
        if old not in presets:
            return self.async_abort(reason="no_presets")

        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input["name"].strip()
            if not name or name.lower() in RESERVED_PRESET_NAMES:
                errors["name"] = "reserved_name"
            elif not user_input["valves"]:
                errors["valves"] = "no_valve"
            else:
                valves = list(user_input["valves"])
                new_presets: dict[str, list[str]] = {}
                for key, value in presets.items():
                    if key == old:
                        new_presets[name] = valves  # stessa posizione, nuovo nome
                    elif key != name:
                        new_presets[key] = value
                order = [
                    name if n == old else n
                    for n in (current.get(CONF_PRESET_ORDER) or [])
                ]
                return self.async_create_entry(
                    data={
                        **self.config_entry.options,
                        CONF_PRESETS: new_presets,
                        CONF_PRESET_ORDER: list(dict.fromkeys(order)),
                    }
                )

        schema = vol.Schema(
            {
                vol.Required("name", default=old): selector.TextSelector(),
                vol.Required(
                    "valves", default=[v for v in presets[old] if v in heaters]
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        include_entities=heaters, multiple=True
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="edit_preset_details", data_schema=schema, errors=errors
        )

    async def async_step_add_slot(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            days = list(user_input.get("days") or [])
            start = str(user_input["start"])[:5]
            end = str(user_input["end"])[:5]
            if not days:
                errors["days"] = "no_day"
            elif start == end:
                errors["end"] = "invalid_time"
            else:
                slots = list(self._current().get(CONF_SCHEDULE_SLOTS) or [])
                slots.append({"days": days, "start": start, "end": end})
                return self.async_create_entry(
                    data={**self.config_entry.options, CONF_SCHEDULE_SLOTS: slots}
                )
        schema = vol.Schema(
            {
                vol.Required(
                    "days", default=["mon", "tue", "wed", "thu", "fri"]
                ): _days_selector(),
                vol.Required("start", default="06:30:00"): selector.TimeSelector(),
                vol.Required("end", default="08:30:00"): selector.TimeSelector(),
            }
        )
        return self.async_show_form(
            step_id="add_slot", data_schema=schema, errors=errors
        )

    async def async_step_edit_slot(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        slots = list(self._current().get(CONF_SCHEDULE_SLOTS) or [])
        if not slots:
            return self.async_abort(reason="no_slots")
        if user_input is not None:
            self._edit_slot = int(user_input["slot"])
            return await self.async_step_edit_slot_details()
        schema = vol.Schema(
            {
                vol.Required("slot"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": str(i), "label": _slot_summary(s, self.hass.config.language)}
                            for i, s in enumerate(slots)
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="edit_slot", data_schema=schema)

    async def async_step_edit_slot_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        slots = list(self._current().get(CONF_SCHEDULE_SLOTS) or [])
        index = self._edit_slot
        if index >= len(slots):
            return self.async_abort(reason="no_slots")
        slot = slots[index]

        errors: dict[str, str] = {}
        if user_input is not None:
            days = list(user_input.get("days") or [])
            start = str(user_input["start"])[:5]
            end = str(user_input["end"])[:5]
            if not days:
                errors["days"] = "no_day"
            elif start == end:
                errors["end"] = "invalid_time"
            else:
                slots[index] = {"days": days, "start": start, "end": end}
                return self.async_create_entry(
                    data={**self.config_entry.options, CONF_SCHEDULE_SLOTS: slots}
                )

        schema = vol.Schema(
            {
                vol.Required("days", default=list(slot["days"])): _days_selector(),
                vol.Required(
                    "start", default=f"{slot['start']}:00"
                ): selector.TimeSelector(),
                vol.Required("end", default=f"{slot['end']}:00"): selector.TimeSelector(),
            }
        )
        return self.async_show_form(
            step_id="edit_slot_details", data_schema=schema, errors=errors
        )

    async def async_step_delete_slot(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        slots = list(self._current().get(CONF_SCHEDULE_SLOTS) or [])
        if not slots:
            return self.async_abort(reason="no_slots")
        if user_input is not None:
            drop = {int(i) for i in user_input["slots"]}
            kept = [s for i, s in enumerate(slots) if i not in drop]
            return self.async_create_entry(
                data={**self.config_entry.options, CONF_SCHEDULE_SLOTS: kept}
            )
        schema = vol.Schema(
            {
                vol.Required("slots"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": str(i), "label": _slot_summary(s, self.hass.config.language)}
                            for i, s in enumerate(slots)
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="delete_slot", data_schema=schema)

    async def async_step_sort_presets(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        current = self._current()
        names = sort_by_order(
            list(current.get(CONF_PRESETS) or {}), current.get(CONF_PRESET_ORDER)
        )
        if len(names) < 2:
            return self.async_abort(reason="no_presets")

        if user_input is not None:
            name = user_input["preset"]
            position = int(user_input["position"])
            names.remove(name)
            names.insert(max(0, min(len(names), position - 1)), name)
            return self.async_create_entry(
                data={**self.config_entry.options, CONF_PRESET_ORDER: names}
            )

        schema = vol.Schema(
            {
                vol.Required("preset"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=names)
                ),
                vol.Required("position", default=1): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=len(names),
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="sort_presets",
            data_schema=schema,
            description_placeholders={"order": " → ".join(names)},
        )

    async def async_step_delete_preset(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        presets = dict(self._current().get(CONF_PRESETS) or {})
        if not presets:
            return self.async_abort(reason="no_presets")
        if user_input is not None:
            for name in user_input["names"]:
                presets.pop(name, None)
            order = [
                n
                for n in (self._current().get(CONF_PRESET_ORDER) or [])
                if n not in user_input["names"]
            ]
            return self.async_create_entry(
                data={
                    **self.config_entry.options,
                    CONF_PRESETS: presets,
                    CONF_PRESET_ORDER: order,
                }
            )
        schema = vol.Schema(
            {
                vol.Required("names"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(presets), multiple=True
                    )
                )
            }
        )
        return self.async_show_form(step_id="delete_preset", data_schema=schema)
