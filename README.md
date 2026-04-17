# Smart Climate

An advanced HACS custom integration for Home Assistant with intelligent climate control for floor heating, air conditioning, and other heating/cooling systems.

---

## Features

### Three control algorithms

| Algorithm | Description |
|-----------|-------------|
| **Hysteresis** | Classic on/off with configurable cold and hot tolerance |
| **PID** | Proportional-Integral-Derivative controller with anti-windup and output limiting |
| **Predictive** | Learns the heating/cooling rate of the room via linear regression |

### Self-learning (Tado-style)
- After each heating session the algorithm calculates the actual °C/min and updates its internal estimate via an **Exponential Moving Average (EMA)**
- Learned rates and PID state are **persistently stored** and survive a Home Assistant restart
- **Early start**: the system automatically calculates when to start heating so the room is at the target temperature exactly at the next schedule change — just like Tado

### Cascade control (primary + secondary source)
The primary source (e.g. AC) always turns on first. The secondary source (e.g. floor heating) only activates if the primary cannot reach the target within the configured time. Can also be used without a secondary source (primary-only).

**Example timeline** — target 20 °C, current 17 °C:
```
00:00  Too cold → AC (primary) turns on
00:30  After 30 min: temp 18.2 °C — 1.8 °C short → Floor heating (secondary) on
00:55  Temperature reaches 20 °C
01:05  Floor heating (after delay) off → AC off
```

| Setting | Default | Description |
|---------|---------|-------------|
| Secondary wait time | 30 min | How long the primary source gets to reach target |
| Temperature shortfall | 1.5 °C | How far below target to activate secondary |
| Deactivation delay | 10 min | Secondary stays on briefly after target is reached |
| **Instant threshold** | 3.0 °C | Larger shortfall → secondary activates immediately, no wait |

### Presets

| Preset | Default | Description |
|--------|---------|-------------|
| Comfort | 20 °C | Daily use |
| Eco | 17 °C | Energy saving |
| Sleep | 16 °C | Night mode |
| Away | 12 °C | Nobody home |
| Boost | 24 °C | Temporary quick heat-up |
| Schedule | — | Follows the weekly schedule |

### Weekly schedule
Configure time blocks per day directly in the options flow UI (Settings → Integrations → Smart Climate → Configure → Weekly schedule). One line per block:

```
[days] [HH:MM] [preset]

Days: mo tu we th fr sa su  (range: mo-fr  /  comma list: mo,we,fr)
Presets: comfort · eco · sleep · away
Lines starting with # are ignored.

Example:
  mo-fr 07:00 comfort
  mo-fr 09:00 eco
  mo-fr 17:30 comfort
  mo-fr 23:00 sleep
  sa-su 08:00 comfort
  sa-su 23:00 sleep
```

You can also set the schedule via a service call:

```yaml
service: smart_climate.set_schedule
target:
  entity_id: climate.living_room
data:
  entries:
    - days: [0, 1, 2, 3, 4]   # mo–fr
      start: "07:00"
      preset: comfort
    - days: [0, 1, 2, 3, 4]
      start: "23:00"
      preset: sleep
    - days: [5, 6]             # sa–su
      start: "08:00"
      preset: comfort
```

### Presence detection
- Link `person`, `device_tracker`, or `binary_sensor` entities
- Automatically switches to **Away** when everyone is gone
- Restores the previous preset on return

### Window detection
- **Window sensor**: link a `binary_sensor` (e.g. a contact switch) directly. When the sensor turns on, heating stops immediately. It resumes automatically when closed.
- **Temperature drop**: detects a rapid temperature drop (configurable threshold and time window) as an alternative without a sensor
- Automatically turns off heating while ventilating
- Resumes after a configurable pause

### Vacation mode
```yaml
service: smart_climate.set_vacation
target:
  entity_id: climate.living_room
data:
  start_date: "2025-07-01"
  end_date: "2025-07-14"
  temperature: 12
```

### Boost
```yaml
service: smart_climate.set_boost
target:
  entity_id: climate.living_room
data:
  duration: 60           # minutes
  target_temperature: 24
```

### Block cooling at low outside temperature
Set an outside temperature threshold (e.g. 16 °C). If it is colder outside, cooling is completely blocked — useful for AC units that would otherwise cool unnecessarily when it is already cold outside.

### Predictive cooling block (weather forecast)
Link a `weather.*` entity to read the hourly forecast. If the minimum predicted temperature within the configurable look-ahead window (default: 12 hours) falls below a threshold (default: 15 °C), cooling is blocked. This prevents wasting energy cooling during the day when you will need that warmth in the evening.

| Setting | Default | Description |
|---------|---------|-------------|
| Weather entity | — | `weather.*` entity with hourly forecast |
| Forecast threshold | 15 °C | Block cooling if predicted min falls below this |
| Look-ahead window | 12 h | How many hours ahead to check |

State attributes on the entity:
- `forecast_cool_blocked` — `true` when cooling is being suppressed by forecast
- `forecast_min_temp_next_hours` — lowest forecast temperature found in the window

> **Note:** works best with integrations that provide hourly forecasts (e.g. Buienradar, Met.no). Daily-only forecasts are supported but less precise.

### Gradual temperature transition (ramp)
When changing a preset or target temperature, the setpoint climbs step by step towards the new target. This prevents the heater from running at full power for a large jump (e.g. Eco → Comfort), allowing the room to warm up gradually.

| Setting | Default | Description |
|---------|---------|-------------|
| Step size | 0.5 °C | Temperature increment per step |
| Step interval | 5 min | Wait time between steps |

### Delay notification
Trigger a notification if the room has not reached its target after a configurable number of minutes. The notification appears in Home Assistant and disappears automatically once the target is reached or the thermostat is turned off. Optionally sends a push message via a `notify.*` service (e.g. your mobile app).

### Frost protection
Set a minimum temperature (e.g. 5 °C). If the room temperature drops below this, heating activates automatically — even when the thermostat is set to OFF. Prevents frozen pipes during extended absence.

### Sensor failsafe
If the temperature sensor has not sent an update for longer than the configured time (e.g. 30 minutes), the system turns off all heating/cooling. Prevents heating from running indefinitely when a sensor is broken or has lost connection.

### Humidity comfort correction
Link a humidity sensor. At high humidity a temperature feels warmer, so the target temperature is automatically reduced slightly (and vice versa). The correction is configurable with a reference humidity and a comfort factor (°C per % deviation).

> **Note:** humidity correction is only active in pure **heating mode (HEAT)**. In cooling mode (COOL / Heat-Cool) the configured target temperature always applies without adjustment.

### Energy price setback
Link an energy price sensor (e.g. Nordpool or ENTSO-E). When the electricity price rises above the threshold, the target temperature is automatically reduced (when heating) or raised (when cooling) by the configured setback value. The system returns to the original target automatically when the price drops.

### Hold mode (temporary temperature override)
Override the target temperature for a set duration via a service. After the duration the system automatically returns to the previous target (preset or schedule).

```yaml
service: smart_climate.set_hold
target:
  entity_id: climate.living_room
data:
  temperature: 22
  duration: 120   # minutes
```

```yaml
service: smart_climate.clear_hold
target:
  entity_id: climate.living_room
```

### Season detection (auto HEAT/COOL)
Set two threshold temperatures based on outside temperature. The system automatically switches between heating and cooling mode when the outside temperature crosses a threshold. No need to switch modes manually at season transitions.

| Setting | Default | Description |
|---------|---------|-------------|
| Cooling threshold | 22 °C outside | Above this → COOL |
| Heating threshold | 18 °C outside | Below this → HEAT |

### Vacation calendar (HA calendar)
Link a Home Assistant calendar entity as a vacation calendar. When an active vacation event is found, Smart Climate automatically switches to the **Away** preset. When the event ends, the system returns to normal operation.

### Weather compensation
Adjusts the target temperature based on the outside temperature via a configurable slope (heating curve). In cold weather the heating setpoint is automatically raised.

> **Note:** weather compensation is only active in pure **heating mode (HEAT)**. In cooling mode (COOL / Heat-Cool) the configured target temperature always applies without adjustment.

### Multi-split outdoor unit coordination
Multiple indoor zones sharing one outdoor unit cannot heat and cool at the same time. Assign all zones in the same group the same **group ID** (e.g. `home_split`). Smart Climate uses weighted voting to decide whether the group heats or cools:

- Each zone votes based on its temperature deviation from target (> 0.5 °C deadband)
- **Priority override**: if any zone deviates ≥ the priority threshold (default 3 °C), that direction wins immediately
- **Weighted majority**: if one direction leads by more than the switch margin (default 1 °C), that direction wins
- **Tie**: current group mode is kept (prevents flip-flopping)

Zones blocked by the group decision have their actuators turned off automatically.

State attributes on each zone entity:
- `multisplit_group` — the configured group ID
- `multisplit_group_mode` — current group decision (`heat` / `cool` / `null`)

### Floor heating pump
- **Follows zones**: pump on when one or more zones have a heating demand
- **Post-heat run time**: keeps running after all zones close (distributes residual heat)
- **Minimum run time**: protects the pump from rapid on/off cycling
- **Anti-seize**: automatically runs for 30 minutes every 24 hours (configurable) to prevent seizing
- **Preferred time**: anti-seize exercise runs preferably at 02:00 (configurable)
- **Manual trigger**:

```yaml
service: smart_climate.trigger_pump_exercise
target:
  entity_id: switch.floor_heating_pump
data:
  duration: 30   # minutes (optional)
```

---

## Entities per zone

| Platform | Entity | Description |
|----------|--------|-------------|
| `climate` | `climate.<name>` | Thermostat with presets and HVAC modes |
| `sensor` | `sensor.<name>_heater_runtime` | Hours of heating today |
| `sensor` | `sensor.<name>_cooler_runtime` | Hours of cooling today |
| `sensor` | `sensor.<name>_heater_energy` | kWh heating today (requires watt > 0) |
| `sensor` | `sensor.<name>_cooler_energy` | kWh cooling today (requires watt > 0) |
| `sensor` | `sensor.<name>_effective_target` | Actual setpoint including all corrections (°C) |
| `sensor` | `sensor.<name>_heating_rate` | Learned °C/min (EMA over sessions) |
| `sensor` | `sensor.<name>_time_to_target` | Estimated minutes to target temperature |
| `sensor` | `sensor.<name>_next_schedule` | Next schedule transition (e.g. "Thu 17:30 → comfort") |
| `sensor` | `sensor.<name>_pid_output` | PID output value 0–100 % (PID only) |
| `sensor` | `sensor.<name>_hold_remaining` | Remaining minutes in hold mode |
| `binary_sensor` | `binary_sensor.<name>_price_setback_active` | On when energy price setback is active |
| `number` | `number.<name>_pid_kp` | PID Kp — live adjustable |
| `number` | `number.<name>_pid_ki` | PID Ki — live adjustable |
| `number` | `number.<name>_pid_kd` | PID Kd — live adjustable |
| `select` | `select.<name>_algorithm` | Switch algorithm without restart |
| `switch` | `switch.<name>_pump` | Pump manager with anti-seize |

---

## Installation

### Via HACS (recommended)
1. In Home Assistant go to **HACS → Integrations**
2. Click the three dots top-right → **Custom repositories**
3. Add: `https://github.com/doublesytems/Climate-control` — category: **Integration**
4. Search for **Smart Climate** and install
5. Restart Home Assistant
6. Go to **Settings → Integrations → + Add → Smart Climate**

### Manual
1. Copy the folder `custom_components/smart_climate/` to `config/custom_components/smart_climate/`
2. Restart Home Assistant
3. Add the integration via the UI

---

## Configuration wizard

The integration is configured via an 8-step wizard in the Home Assistant UI:

1. **Device** — temperature sensor, heater, cooler, outside sensor
2. **Algorithm** — choice + basic parameters (tolerance, min/max temp)
3. **PID parameters** — Kp, Ki, Kd (only shown for PID algorithm)
4. **Presets** — temperature per preset + boost duration
5. **Advanced** — presence, window sensor, window detection, block cooling, weather compensation, AC idle mode, temperature ramp, notification, frost protection, sensor failsafe, humidity correction, energy price setback, season detection, vacation calendar, weather forecast block
6. **Multi-split** — group ID, priority threshold, switch margin
7. **Cascade** — primary source (AC), secondary source (floor), wait time, shortfall threshold, instant threshold
8. **Pump** — pump entity, zones, anti-seize, post-heat delay, early start
9. **Weekly schedule** — schedule in text format (one line per block)

All settings can be changed afterwards via **Integrations → Smart Climate → Configure**.

### Diagnostics
Via **Settings → Integrations → Smart Climate → Diagnostics** you can download a full status overview: active mode, cascade state, learned heating rate, PID integral, ramp target and more. Useful when reporting issues.

---

## Extra state attributes

The thermostat entity exposes among others:

| Attribute | Description |
|-----------|-------------|
| `algorithm` | Active control algorithm |
| `learned_heating_rate_c_per_min` | Learned heating rate |
| `early_start_active` | Early start active |
| `window_open` | Window open detected |
| `presence_detected` | Presence |
| `weather_temp_adjustment` | Weather compensation offset (°C) |
| `pid_output` | PID output value (0–100) |
| `predicted_reach_time_min` | Estimated time to target temperature (min) |
| `boost_remaining_min` | Remaining boost time |
| `heater_runtime_today_h` | Heating time today (hours) |
| `cascade_primary_on` | Primary source (AC) active |
| `cascade_secondary_on` | Secondary source (floor) active |
| `cascade_reason` | Reason for current cascade state |
| `cascade_secondary_since_min` | Minutes the secondary source has been active |
| `hold_temp` | Hold target temperature |
| `hold_remaining_h` | Remaining hold time (hours) |
| `frost_active` | Frost protection active |
| `humidity_adjustment` | Humidity correction offset (°C) |
| `price_setback_active` | Energy price setback active |
| `auto_mode` | Season detection enabled |
| `multisplit_group` | Multi-split group ID |
| `multisplit_group_mode` | Current group decision (heat / cool) |
| `forecast_cool_blocked` | Cooling blocked by weather forecast |
| `forecast_min_temp_next_hours` | Lowest forecast temperature in look-ahead window (°C) |

---

## License

MIT License — free to use and modify.
