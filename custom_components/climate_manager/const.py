"""Constants for Climate Manager."""

DOMAIN = "climate_manager"

CONF_SENSOR = "sensor"
CONF_HEATER = "heater"
CONF_BOILER = "boiler"
CONF_PRESETS = "presets"
CONF_PRESET_ORDER = "preset_order"
CONF_BOILER_SETPOINT = "boiler_setpoint"
CONF_OVERRIDE_ENTITY = "override_entity"
CONF_OVERRIDE_VALUE = "override_value"
CONF_SCHEDULE = "schedule"
CONF_SCHEDULE_SLOTS = "schedule_slots"
CONF_COMFORT_TEMP = "comfort_temp"
CONF_ECO_TEMP = "eco_temp"
CONF_COOL_COMFORT_TEMP = "cool_comfort_temp"
CONF_COOL_ECO_TEMP = "cool_eco_temp"
CONF_BLOCK_CALENDARS = "block_calendars"
CONF_BLOCK_MODE = "block_mode"
CONF_PUMP = "pump"
CONF_COOLING_ENABLED = "cooling_enabled"
CONF_HOT_TOLERANCE = "hot_tolerance"
CONF_COLD_TOLERANCE = "cold_tolerance"
CONF_MIN_CYCLE = "min_cycle"
CONF_AC = "ac"
CONF_INPUT_TYPE = "input_type"
CONF_CONTACT = "contact"
CONF_CONTACT_INVERT = "contact_invert"
CONF_WINDOWS = "windows"
CONF_WINDOW_DELAY = "window_delay"
CONF_ANTIFREEZE = "antifreeze_temp"
CONF_HYSTERESIS = "hysteresis"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"

SETPOINT_MIN = 28.0
SETPOINT_MAX = 70.0
DEFAULT_SETPOINT = 28.0
DEFAULT_OVERRIDE_VALUE = 55.0
DEFAULT_COMFORT_TEMP = 20.0
DEFAULT_ECO_TEMP = 17.0
DEFAULT_COOL_COMFORT_TEMP = 26.0
DEFAULT_COOL_ECO_TEMP = 28.0
SEASON_WINTER = "winter"
SEASON_SUMMER = "summer"
BLOCK_OFF = "off"
BLOCK_ECO = "eco"
DEFAULT_HYSTERESIS = 0.3
DEFAULT_ANTIFREEZE = 5.0
ANTIFREEZE_MARGIN = 1.0
DEFAULT_WINDOW_DELAY = 1.0
INPUT_TEMPERATURE = "temperature"
INPUT_CONTACT = "contact"
HEAT_SOURCE_HEATING = "heating"
HEAT_SOURCE_AC = "ac"
HEAT_SOURCE_BOTH = "both"
DEFAULT_COOL_TARGET = 26.0
DEFAULT_MIN_TEMP = 15.0
DEFAULT_MAX_TEMP = 30.0
DEFAULT_TARGET_TEMP = 20.0


def get_heaters(cfg: dict) -> list[str]:
    """Restituisce la lista dei relè/elettrovalvole (accetta anche il vecchio formato singolo)."""
    value = cfg[CONF_HEATER]
    return [value] if isinstance(value, str) else list(value)


def sort_by_order(names: list[str], order: list[str] | None) -> list[str]:
    """Ordina i nomi secondo la lista 'order'; quelli non presenti vanno in fondo."""
    order = list(order or [])
    names = list(names)
    return sorted(
        names,
        key=lambda n: order.index(n) if n in order else len(order) + names.index(n),
    )


DAY_INDEX = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _to_minutes(value: str) -> int:
    hours, minutes = str(value).split(":")[:2]
    return int(hours) * 60 + int(minutes)


def parse_slots(raw: list[dict] | None) -> list[tuple[set[int], int, int]]:
    """Converte le fasce salvate in (giorni, minuto_inizio, minuto_fine)."""
    slots = []
    for slot in raw or []:
        try:
            days = {DAY_INDEX[d] for d in slot["days"]}
            slots.append((days, _to_minutes(slot["start"]), _to_minutes(slot["end"])))
        except (KeyError, ValueError):
            continue
    return slots


def slot_active(slots: list[tuple[set[int], int, int]], weekday: int, minutes: int) -> bool:
    """True se l'istante cade dentro una fascia (gestisce quelle oltre mezzanotte)."""
    for days, start, end in slots:
        if start < end:
            if weekday in days and start <= minutes < end:
                return True
        else:  # la fascia passa la mezzanotte
            if weekday in days and minutes >= start:
                return True
            if (weekday - 1) % 7 in days and minutes < end:
                return True
    return False


def get_shared_setpoint(hass, entity_id: str) -> dict:
    """Setpoint caldaia unico: condiviso da tutti i termostati con la stessa caldaia."""
    return hass.data[DOMAIN].setdefault("sp_shared", {}).setdefault(
        entity_id,
        {"value": DEFAULT_SETPOINT, "ready": False, "zones": set(), "numbers": set()},
    )


DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_SHORT = {
    "it": {"mon": "Lun", "tue": "Mar", "wed": "Mer", "thu": "Gio",
           "fri": "Ven", "sat": "Sab", "sun": "Dom"},
    "en": {"mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu",
           "fri": "Fri", "sat": "Sat", "sun": "Sun"},
}
EVERY_DAY = {"it": "Tutti i giorni", "en": "Every day"}
NEW_SLOT_LABEL = {"it": "Nuova fascia", "en": "New slot"}
NO_SLOTS_LABEL = {
    "it": "nessuna fascia (aggiungine una per usare la modalità Auto)",
    "en": "no slots (add one to use Auto mode)",
}


def lang_of(language: str | None) -> str:
    """Lingua supportata ("it" o "en") a partire da quella di Home Assistant."""
    return "it" if (language or "").lower().startswith("it") else "en"


def slot_summary(slot: dict, language: str | None = None) -> str:
    """Short slot description, e.g. "Mon, Tue 06:30–08:30"."""
    lang = lang_of(language)
    days = slot.get("days", [])
    if len(days) == 7:
        label = EVERY_DAY[lang]
    else:
        label = ", ".join(DAY_SHORT[lang][d] for d in DAY_ORDER if d in days)
    return f"{label} {slot.get('start')}–{slot.get('end')}"
