"""Config flow for Smart Climate integration (full-featured)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    ALGORITHMS,
    ALGORITHM_HYSTERESIS,
    ALGORITHM_PID,
    CONF_AC_MODE,
    CONF_ALGORITHM,
    CONF_BOOST_DURATION,
    CONF_COLD_TOLERANCE,
    CONF_COOLER,
    CONF_COOLER_WATT,
    CONF_CASCADE_DEACTIVATE_DELAY,
    CONF_CASCADE_ENABLED,
    CONF_CASCADE_PRIMARY_COOLER,
    CONF_CASCADE_PRIMARY_HEATER,
    CONF_CASCADE_TEMP_THRESHOLD,
    CONF_CASCADE_TIMEOUT,
    CONF_EARLY_START,
    CONF_HEATER,
    CONF_HEATER_WATT,
    CONF_HOT_TOLERANCE,
    CONF_KEEP_ALIVE,
    CONF_LEARNING_ENABLED,
    CONF_MAX_TEMP,
    CONF_MIN_CYCLE_DURATION,
    CONF_MIN_TEMP,
    CONF_PID_KD,
    CONF_PID_KI,
    CONF_PID_KP,
    CONF_PRESET_AWAY_TEMP,
    CONF_PRESET_BOOST_TEMP,
    CONF_PRESET_COMFORT_TEMP,
    CONF_PRESET_ECO_TEMP,
    CONF_PRESET_SLEEP_TEMP,
    CONF_PRESENCE_SENSORS,
    CONF_PUMP_ANTI_SEIZE_DURATION,
    CONF_PUMP_ANTI_SEIZE_INTERVAL,
    CONF_PUMP_ENTITY,
    CONF_PUMP_EXERCISE_TIME,
    CONF_PUMP_MIN_RUN_TIME,
    CONF_PUMP_POST_HEAT_DELAY,
    CONF_PUMP_ZONE_ENTITIES,
    CONF_SENSOR,
    CONF_SENSOR_OUTSIDE,
    CONF_TARGET_TEMP,
    CONF_WEATHER_COMPENSATION,
    CONF_WEATHER_OUTSIDE_REF,
    CONF_WEATHER_SLOPE,
    CONF_WINDOW_DETECTION,
    CONF_WINDOW_OPEN_DURATION,
    CONF_WINDOW_TEMP_DROP,
    CONF_WINDOW_TEMP_DROP_TIME,
    DEFAULT_BOOST_DURATION,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_PID_KD,
    DEFAULT_PID_KI,
    DEFAULT_PID_KP,
    DEFAULT_PRESET_AWAY,
    DEFAULT_PRESET_BOOST,
    DEFAULT_PRESET_COMFORT,
    DEFAULT_PRESET_ECO,
    DEFAULT_PRESET_SLEEP,
    DEFAULT_PUMP_ANTI_SEIZE_DURATION,
    DEFAULT_PUMP_ANTI_SEIZE_INTERVAL,
    DEFAULT_CASCADE_DEACTIVATE_DELAY,
    DEFAULT_CASCADE_TEMP_THRESHOLD,
    DEFAULT_CASCADE_TIMEOUT,
    DEFAULT_PUMP_EXERCISE_TIME,
    DEFAULT_PUMP_MIN_RUN_TIME,
    DEFAULT_PUMP_POST_HEAT_DELAY,
    DEFAULT_TARGET_TEMP,
    DEFAULT_TOLERANCE,
    DEFAULT_WEATHER_OUTSIDE_REF,
    DEFAULT_WEATHER_SLOPE,
    DEFAULT_WINDOW_OPEN_DURATION,
    DEFAULT_WINDOW_TEMP_DROP,
    DEFAULT_WINDOW_TEMP_DROP_TIME,
    DOMAIN,
)

# ---------------------------------------------------------------------------
# Step schemas
# ---------------------------------------------------------------------------

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Optional(CONF_HEATER): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["switch", "climate", "input_boolean"])
        ),
        vol.Optional(CONF_COOLER): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["switch", "climate", "input_boolean"])
        ),
        vol.Optional(CONF_SENSOR_OUTSIDE): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Optional(CONF_AC_MODE, default=False): selector.BooleanSelector(),
    }
)

STEP_ALGORITHM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ALGORITHM, default=ALGORITHM_HYSTERESIS): selector.SelectSelector(
            selector.SelectSelectorConfig(options=ALGORITHMS, translation_key="algorithm")
        ),
        vol.Optional(CONF_TARGET_TEMP, default=DEFAULT_TARGET_TEMP): selector.NumberSelector(
            selector.NumberSelectorConfig(min=5.0, max=40.0, step=0.5, mode="box")
        ),
        vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.0, max=20.0, step=0.5, mode="box")
        ),
        vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): selector.NumberSelector(
            selector.NumberSelectorConfig(min=20.0, max=50.0, step=0.5, mode="box")
        ),
        vol.Optional(CONF_COLD_TOLERANCE, default=DEFAULT_TOLERANCE): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.1, max=5.0, step=0.1, mode="box")
        ),
        vol.Optional(CONF_HOT_TOLERANCE, default=DEFAULT_TOLERANCE): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.1, max=5.0, step=0.1, mode="box")
        ),
        vol.Optional(CONF_MIN_CYCLE_DURATION, default=10): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=300, step=5, mode="box")
        ),
        vol.Optional(CONF_KEEP_ALIVE, default=30): selector.NumberSelector(
            selector.NumberSelectorConfig(min=10, max=300, step=10, mode="box")
        ),
    }
)

STEP_PID_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PID_KP, default=DEFAULT_PID_KP): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.0, max=100.0, step=0.1, mode="box")
        ),
        vol.Optional(CONF_PID_KI, default=DEFAULT_PID_KI): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.0, max=10.0, step=0.01, mode="box")
        ),
        vol.Optional(CONF_PID_KD, default=DEFAULT_PID_KD): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.0, max=100.0, step=0.1, mode="box")
        ),
    }
)

STEP_PRESETS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PRESET_COMFORT_TEMP, default=DEFAULT_PRESET_COMFORT): selector.NumberSelector(
            selector.NumberSelectorConfig(min=15.0, max=30.0, step=0.5, mode="box")
        ),
        vol.Optional(CONF_PRESET_ECO_TEMP, default=DEFAULT_PRESET_ECO): selector.NumberSelector(
            selector.NumberSelectorConfig(min=10.0, max=25.0, step=0.5, mode="box")
        ),
        vol.Optional(CONF_PRESET_SLEEP_TEMP, default=DEFAULT_PRESET_SLEEP): selector.NumberSelector(
            selector.NumberSelectorConfig(min=10.0, max=22.0, step=0.5, mode="box")
        ),
        vol.Optional(CONF_PRESET_AWAY_TEMP, default=DEFAULT_PRESET_AWAY): selector.NumberSelector(
            selector.NumberSelectorConfig(min=5.0, max=18.0, step=0.5, mode="box")
        ),
        vol.Optional(CONF_PRESET_BOOST_TEMP, default=DEFAULT_PRESET_BOOST): selector.NumberSelector(
            selector.NumberSelectorConfig(min=18.0, max=35.0, step=0.5, mode="box")
        ),
        vol.Optional(CONF_BOOST_DURATION, default=DEFAULT_BOOST_DURATION): selector.NumberSelector(
            selector.NumberSelectorConfig(min=5, max=480, step=5, mode="box")
        ),
    }
)

STEP_ADVANCED_SCHEMA = vol.Schema(
    {
        # Presence sensors
        vol.Optional(CONF_PRESENCE_SENSORS): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=["person", "device_tracker", "binary_sensor", "input_boolean"],
                multiple=True,
            )
        ),
        # Window detection
        vol.Optional(CONF_WINDOW_DETECTION, default=False): selector.BooleanSelector(),
        vol.Optional(CONF_WINDOW_TEMP_DROP, default=DEFAULT_WINDOW_TEMP_DROP): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.5, max=5.0, step=0.1, mode="box")
        ),
        vol.Optional(CONF_WINDOW_TEMP_DROP_TIME, default=DEFAULT_WINDOW_TEMP_DROP_TIME): selector.NumberSelector(
            selector.NumberSelectorConfig(min=1, max=30, step=1, mode="box")
        ),
        vol.Optional(CONF_WINDOW_OPEN_DURATION, default=DEFAULT_WINDOW_OPEN_DURATION): selector.NumberSelector(
            selector.NumberSelectorConfig(min=1, max=120, step=1, mode="box")
        ),
        # Weather compensation
        vol.Optional(CONF_WEATHER_COMPENSATION, default=False): selector.BooleanSelector(),
        vol.Optional(CONF_WEATHER_SLOPE, default=DEFAULT_WEATHER_SLOPE): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.0, max=5.0, step=0.1, mode="box")
        ),
        vol.Optional(CONF_WEATHER_OUTSIDE_REF, default=DEFAULT_WEATHER_OUTSIDE_REF): selector.NumberSelector(
            selector.NumberSelectorConfig(min=-10.0, max=25.0, step=0.5, mode="box")
        ),
        # Energy
        vol.Optional(CONF_HEATER_WATT, default=0): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=10000, step=50, mode="box")
        ),
        vol.Optional(CONF_COOLER_WATT, default=0): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=10000, step=50, mode="box")
        ),
    }
)


# ---------------------------------------------------------------------------
# Config flow
# ---------------------------------------------------------------------------

class SmartClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Climate."""

    VERSION = 2

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_HEATER) and not user_input.get(CONF_COOLER):
                errors["base"] = "no_actuator"
            else:
                self._data.update(user_input)
                return await self.async_step_algorithm()
        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

    async def async_step_algorithm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            if user_input.get(CONF_ALGORITHM) == ALGORITHM_PID:
                return await self.async_step_pid()
            return await self.async_step_presets()
        return self.async_show_form(step_id="algorithm", data_schema=STEP_ALGORITHM_SCHEMA)

    async def async_step_pid(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_presets()
        return self.async_show_form(step_id="pid", data_schema=STEP_PID_SCHEMA)

    async def async_step_presets(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_advanced()
        return self.async_show_form(step_id="presets", data_schema=STEP_PRESETS_SCHEMA)

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_cascade()
        return self.async_show_form(step_id="advanced", data_schema=STEP_ADVANCED_SCHEMA)

    async def async_step_cascade(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Optionele cascade-configuratie (primaire + secundaire verwarming/koeling)."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_pump()

        cascade_schema = vol.Schema(
            {
                vol.Optional(CONF_CASCADE_ENABLED, default=False): selector.BooleanSelector(),
                vol.Optional(CONF_CASCADE_PRIMARY_HEATER): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["climate", "switch", "input_boolean"]
                    )
                ),
                vol.Optional(CONF_CASCADE_PRIMARY_COOLER): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["climate", "switch", "input_boolean"]
                    )
                ),
                vol.Optional(CONF_CASCADE_TIMEOUT, default=DEFAULT_CASCADE_TIMEOUT): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=120, step=5, mode="box")
                ),
                vol.Optional(CONF_CASCADE_TEMP_THRESHOLD, default=DEFAULT_CASCADE_TEMP_THRESHOLD): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.5, max=5.0, step=0.5, mode="box")
                ),
                vol.Optional(CONF_CASCADE_DEACTIVATE_DELAY, default=DEFAULT_CASCADE_DEACTIVATE_DELAY): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=60, step=5, mode="box")
                ),
            }
        )
        return self.async_show_form(step_id="cascade", data_schema=cascade_schema)

    async def async_step_pump(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Optional pump controller configuration."""
        if user_input is not None:
            self._data.update(user_input)
            return self._create_entry()

        pump_schema = vol.Schema(
            {
                vol.Optional(CONF_PUMP_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["switch", "input_boolean"]
                    )
                ),
                vol.Optional(CONF_PUMP_ZONE_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["switch", "climate", "input_boolean"],
                        multiple=True,
                    )
                ),
                vol.Optional(CONF_PUMP_ANTI_SEIZE_INTERVAL, default=DEFAULT_PUMP_ANTI_SEIZE_INTERVAL): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=168, step=1, mode="box")
                ),
                vol.Optional(CONF_PUMP_ANTI_SEIZE_DURATION, default=DEFAULT_PUMP_ANTI_SEIZE_DURATION): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=120, step=5, mode="box")
                ),
                vol.Optional(CONF_PUMP_POST_HEAT_DELAY, default=DEFAULT_PUMP_POST_HEAT_DELAY): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=60, step=1, mode="box")
                ),
                vol.Optional(CONF_PUMP_MIN_RUN_TIME, default=DEFAULT_PUMP_MIN_RUN_TIME): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=600, step=10, mode="box")
                ),
                vol.Optional(CONF_PUMP_EXERCISE_TIME, default=DEFAULT_PUMP_EXERCISE_TIME): selector.TimeSelector(),
                vol.Optional(CONF_LEARNING_ENABLED, default=True): selector.BooleanSelector(),
                vol.Optional(CONF_EARLY_START, default=True): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="pump", data_schema=pump_schema)

    def _create_entry(self) -> config_entries.FlowResult:
        name = self._data.pop(CONF_NAME)
        return self.async_create_entry(title=name, data=self._data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "SmartClimateOptionsFlow":
        return SmartClimateOptionsFlow()


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------

class SmartClimateOptionsFlow(config_entries.OptionsFlow):
    """Options flow — allows changing settings without re-adding."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 1 — algorithm & tolerances."""
        cur = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_presets_opt()

        schema = vol.Schema(
            {
                vol.Optional(CONF_ALGORITHM, default=cur.get(CONF_ALGORITHM, ALGORITHM_HYSTERESIS)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=ALGORITHMS, translation_key="algorithm")
                ),
                vol.Optional(CONF_COLD_TOLERANCE, default=cur.get(CONF_COLD_TOLERANCE, DEFAULT_TOLERANCE)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.1, max=5.0, step=0.1, mode="box")
                ),
                vol.Optional(CONF_HOT_TOLERANCE, default=cur.get(CONF_HOT_TOLERANCE, DEFAULT_TOLERANCE)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.1, max=5.0, step=0.1, mode="box")
                ),
                vol.Optional(CONF_PID_KP, default=cur.get(CONF_PID_KP, DEFAULT_PID_KP)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.0, max=100.0, step=0.1, mode="box")
                ),
                vol.Optional(CONF_PID_KI, default=cur.get(CONF_PID_KI, DEFAULT_PID_KI)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.0, max=10.0, step=0.01, mode="box")
                ),
                vol.Optional(CONF_PID_KD, default=cur.get(CONF_PID_KD, DEFAULT_PID_KD)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.0, max=100.0, step=0.1, mode="box")
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_presets_opt(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 2 — preset temperatures."""
        cur = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_advanced_opt()

        schema = vol.Schema(
            {
                vol.Optional(CONF_PRESET_COMFORT_TEMP, default=cur.get(CONF_PRESET_COMFORT_TEMP, DEFAULT_PRESET_COMFORT)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=15.0, max=30.0, step=0.5, mode="box")
                ),
                vol.Optional(CONF_PRESET_ECO_TEMP, default=cur.get(CONF_PRESET_ECO_TEMP, DEFAULT_PRESET_ECO)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10.0, max=25.0, step=0.5, mode="box")
                ),
                vol.Optional(CONF_PRESET_SLEEP_TEMP, default=cur.get(CONF_PRESET_SLEEP_TEMP, DEFAULT_PRESET_SLEEP)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10.0, max=22.0, step=0.5, mode="box")
                ),
                vol.Optional(CONF_PRESET_AWAY_TEMP, default=cur.get(CONF_PRESET_AWAY_TEMP, DEFAULT_PRESET_AWAY)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5.0, max=18.0, step=0.5, mode="box")
                ),
                vol.Optional(CONF_PRESET_BOOST_TEMP, default=cur.get(CONF_PRESET_BOOST_TEMP, DEFAULT_PRESET_BOOST)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=18.0, max=35.0, step=0.5, mode="box")
                ),
                vol.Optional(CONF_BOOST_DURATION, default=cur.get(CONF_BOOST_DURATION, DEFAULT_BOOST_DURATION)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=480, step=5, mode="box")
                ),
            }
        )
        return self.async_show_form(step_id="presets_opt", data_schema=schema)

    async def async_step_advanced_opt(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 3 — presence, window, weather, energy."""
        cur = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="", data=self._data)

        schema = vol.Schema(
            {
                vol.Optional(CONF_PRESENCE_SENSORS, default=cur.get(CONF_PRESENCE_SENSORS, [])): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["person", "device_tracker", "binary_sensor", "input_boolean"],
                        multiple=True,
                    )
                ),
                vol.Optional(CONF_WINDOW_DETECTION, default=cur.get(CONF_WINDOW_DETECTION, False)): selector.BooleanSelector(),
                vol.Optional(CONF_WINDOW_TEMP_DROP, default=cur.get(CONF_WINDOW_TEMP_DROP, DEFAULT_WINDOW_TEMP_DROP)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.5, max=5.0, step=0.1, mode="box")
                ),
                vol.Optional(CONF_WINDOW_TEMP_DROP_TIME, default=cur.get(CONF_WINDOW_TEMP_DROP_TIME, DEFAULT_WINDOW_TEMP_DROP_TIME)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=30, step=1, mode="box")
                ),
                vol.Optional(CONF_WINDOW_OPEN_DURATION, default=cur.get(CONF_WINDOW_OPEN_DURATION, DEFAULT_WINDOW_OPEN_DURATION)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=120, step=1, mode="box")
                ),
                vol.Optional(CONF_WEATHER_COMPENSATION, default=cur.get(CONF_WEATHER_COMPENSATION, False)): selector.BooleanSelector(),
                vol.Optional(CONF_WEATHER_SLOPE, default=cur.get(CONF_WEATHER_SLOPE, DEFAULT_WEATHER_SLOPE)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.0, max=5.0, step=0.1, mode="box")
                ),
                vol.Optional(CONF_WEATHER_OUTSIDE_REF, default=cur.get(CONF_WEATHER_OUTSIDE_REF, DEFAULT_WEATHER_OUTSIDE_REF)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-10.0, max=25.0, step=0.5, mode="box")
                ),
                vol.Optional(CONF_HEATER_WATT, default=cur.get(CONF_HEATER_WATT, 0)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=10000, step=50, mode="box")
                ),
                vol.Optional(CONF_COOLER_WATT, default=cur.get(CONF_COOLER_WATT, 0)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=10000, step=50, mode="box")
                ),
            }
        )
        return self.async_show_form(step_id="advanced_opt", data_schema=schema)
