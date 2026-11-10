# Climate Manager

[🇮🇹 Italiano](README.md) · 🇬🇧 English

A custom integration for Home Assistant that manages heating and cooling zones: one thermostat per zone, with valves, boiler, pump, air conditioner, time slots, windows and antifreeze.

Each zone becomes a `climate` entity plus a few supporting entities, and everything is configured from the UI, with no YAML.

## Features

- **Choice of input:** temperature sensor or physical thermostat (closed contact = heat request).
- **Outputs:** one or more valves/relays, boiler start output, pump output, air conditioner.
- **Modes:** Off, Heat, Cool (if enabled) and Auto (with time slots).
- **Presets:** choose which valves stay active (useful when a zone has several valves).
- **Boiler setpoint:** a single setpoint shared by all zones using the same boiler, with an override value.
- **Time slots:** comfort temperature inside the slots, reduced temperature outside. They work with both the sensor and the physical thermostat.
- **Blocking calendars:** if a calendar is active, the schedule is blocked (heating turns off or uses the reduced temperature).
- **Windows:** if a window stays open longer than the delay, the zone's heating is suspended.
- **Antifreeze:** below the set temperature the zone always heats, even when off.
- **Heat - cool source:** with an air conditioner configured, choose whether heat comes from the heating system, the air conditioner, or both.

## Installation

### Manual
1. Copy the `climate_manager` folder into `config/custom_components/`.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and search for **Climate Manager**.

### HACS
Once published: HACS → Integrations → ⋮ menu → Custom repositories → paste the repository URL, category *Integration* → install and restart.

> If you are coming from the earlier version called "Termostati" (folder `radiant`): delete the old integration, remove the `radiant` folder, install `climate_manager`, restart and recreate your thermostats with the same names.

## Creating a thermostat

Add the integration once **per zone**. The form asks for:

| Field | Meaning |
|---|---|
| Name | Zone name (must be unique) |
| Relays / valves | One or more `switch` or `input_boolean` entities to control |
| Input type | Temperature sensor or physical thermostat |
| Temperature sensor | Any `sensor` (Modbus probes included) |
| Physical thermostat contact | `binary_sensor`, `switch` or `input_boolean` |
| Inverted contact | Turn on if an open contact means a heat request |
| Boiler / pump output | Optional: switched on when the zone calls for heat |
| Air conditioner | Optional: a `climate`, `switch` or `input_boolean` entity |
| Boiler setpoint | Optional: a `number` or `input_number` (for example the one read by your ESP8266) |
| Override entity | When on, the boiler uses the override setpoint |
| Override setpoint | Value used while the override is active |
| Comfort / reduced temperature | Used in Auto mode inside and outside the slots |
| Blocking calendars and mode | What to do when a calendar is active |
| Window sensor / delay | Opening sensors and minutes before suspending |
| Antifreeze temperature | Below this the zone always heats. 0 = disabled |
| Enable cooling mode | Shows the Cool mode (needs the air conditioner) |
| Heating / cooling tolerance | Hysteresis for switching on and off |
| Minimum on-cycle | Minimum minutes of operation, 0 = disabled |
| Minimum / maximum temperature | Thermostat limits (15 and 30 °C by default) |

You can change every setting later: **Devices & services → Climate Manager → Configure**.

## Entities

For each zone the device contains:

**Controls**
- The **thermostat** (`climate`), with presets for the valves.
- **Heat - cool source:** only if an air conditioner is configured.
- **Boiler setpoint:** only if the setpoint is configured. It is shared: the other zones using the same boiler create it disabled.
- A **"… enabled"** switch for each valve, if the zone has at least two. It excludes a valve without changing preset.

**Configuration (slot editor for dashboards)**
They let you create and edit time slots without opening the options menu. They are named so they sort in order:

1. 01 Slot: picks which slot to edit, or "New slot"
2. 02–08 Slot Monday … Sunday: the days
3. 09 Time slot start
4. 10 Time slot end
5. 11 Save time slot
6. 12 Delete slot
7. 13 Delete all slots

To create a slot: leave "New slot", turn on the days, set start and end, press **Save**. To edit one: pick it in the selector, change the values and press **Save**. If the end is before the start, the slot crosses midnight.

These entities are in the *Configuration* section and do not appear in auto-generated dashboards: add them by hand to your cards.

## How it works

### Thermostat with a sensor
It heats when the temperature drops below the target minus the *heating tolerance* and stops when it goes above the target plus the tolerance. Cooling works the same way with the *cooling tolerance*. The minimum cycle prevents switching on too often.

### Physical thermostat
The zone heats when the contact asks for heat. Time slots, if present, decide when the contact is listened to.

### Auto mode
Available when at least one slot exists. Inside the slots it uses the comfort temperature, outside the reduced one. If you change the temperature by hand, the change lasts until the next slot change. With a physical thermostat, heating stays off outside the slots.

### Boiler, pump and setpoint
The boiler and the pump switch on when at least one zone calls for heat and only for heating (never in Cool mode). The boiler setpoint is shared: if the override entity is on, the override setpoint is written.

### Air conditioner and source
- **Cooling** always uses the air conditioner.
- **Heating** uses the selected source: Heating, Air conditioner, or Heating + Air conditioner together. The combined option works in heat mode only.

### Priority
Antifreeze comes first, then open window and calendar block, then the normal rules.

## Options (Configure menu)

- **Settings and valves**
- **Add / Edit / Change order of / Delete presets** (with at least two valves)
- **Add / Edit / Delete time slots**

## Languages

Italian and English, following the Home Assistant language. Slots use the day abbreviations of the chosen language.

## FAQ

**The boiler setpoint goes back to 28.** That is the minimum allowed value. It happens when no zone calls for heat and there is no saved value: check that the override entity and the setpoint are the right ones.

**I can't see the slot entities.** They are in the *Configuration* section of the device.

**I renamed a zone and the entity IDs stayed old.** Home Assistant does not rename existing entity IDs. Change them from the entity settings.

## Known limitations

The integration was written and checked in code, but has not yet been tested for long on different installations. Please report issues in the repository.

## License

MIT
