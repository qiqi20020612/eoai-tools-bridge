"""One confirmation step with no provider keys or duplicate entries."""

from typing import Any

import probatio as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN, NAME


class ToolsBridgeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure the search bridge."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow installation before the upstream search provider is configured."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title=NAME, data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
