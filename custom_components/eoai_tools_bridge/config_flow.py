"""Key-free setup, explicit permissions and optional Amap credentials."""

from typing import Any

import probatio as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .amap import (
    CONF_AMAP_CITY,
    CONF_AMAP_KEY,
    CONF_AMAP_LOCATION,
    normalize_amap_options,
)
from .const import (
    CONF_ALLOW_SIDE_EFFECTS,
    CONF_ALLOWED_TOOLS,
    CONF_ENABLED,
    DOMAIN,
    NAME,
)
from .policy import normalize_options


class ToolsBridgeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure the tool bridge."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Read current options only after the flow has been initialized."""
        return GatewayOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow installation before the upstream search provider is configured."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title=NAME, data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))


class GatewayOptionsFlow(OptionsFlow):
    """Do not instantiate APIs or invoke tools while changing permissions."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        values = dict(self.config_entry.options)
        if user_input is not None:
            values = user_input
            try:
                options = normalize_options(user_input)
            except vol.Invalid:
                errors["base"] = "invalid_allowlist"
            else:
                try:
                    options.update(normalize_amap_options(user_input))
                except vol.Invalid:
                    errors["base"] = "invalid_amap_options"
                else:
                    return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ENABLED, default=values.get(CONF_ENABLED, False)
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_AMAP_KEY, default=values.get(CONF_AMAP_KEY, "")
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Optional(
                        CONF_AMAP_CITY, default=values.get(CONF_AMAP_CITY, "")
                    ): selector.TextSelector(),
                    vol.Optional(
                        CONF_AMAP_LOCATION, default=values.get(CONF_AMAP_LOCATION, "")
                    ): selector.TextSelector(),
                    vol.Optional(
                        CONF_ALLOWED_TOOLS, default=values.get(CONF_ALLOWED_TOOLS, "")
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
                    vol.Optional(
                        CONF_ALLOW_SIDE_EFFECTS,
                        default=values.get(CONF_ALLOW_SIDE_EFFECTS, False),
                    ): selector.BooleanSelector(),
                }
            ),
            errors=errors,
        )
