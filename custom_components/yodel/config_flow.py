"""Config flow for Yodel integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CAPTUREMOBILE,
    CONF_DATA,
    CONF_EMAIL,
    CONF_ERRORS,
    CONF_MESSAGE,
    CONF_MFA_CODE,
    CONF_MOBILE,
    CONF_USER,
    CONF_VERIFYAPPMOBILENUMBER,
    DOMAIN,
)
from .coordinator import YodelAuthenticationCoordinator, YodelMfaCoordinator

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MOBILE): str,
    }
)
STEP_MFA = vol.Schema(
    {
        vol.Required(CONF_MFA_CODE): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the MFA input allows us to connect."""

    session = async_get_clientsession(hass)
    coordinator = YodelAuthenticationCoordinator(hass, session, data)

    await coordinator.async_refresh()

    if coordinator.last_exception is not None:
        raise coordinator.last_exception

    body = coordinator.data

    err = None

    if CONF_ERRORS in body or len(body[CONF_DATA][CONF_CAPTUREMOBILE][CONF_ERRORS]) > 0:
        if CONF_ERRORS in body:
            err = body[CONF_ERRORS][0][CONF_MESSAGE]
        else:
            err = body[CONF_DATA][CONF_CAPTUREMOBILE][CONF_ERRORS][0]

    return {"title": str(data[CONF_MOBILE]), "data": body, "error": err}


async def validate_mfa_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate the MFA input allows us to connect."""

    session = async_get_clientsession(hass)
    coordinator = YodelMfaCoordinator(hass, session, data)

    await coordinator.async_refresh()

    if coordinator.last_exception is not None:
        raise coordinator.last_exception

    body = coordinator.data

    err = None

    if CONF_ERRORS in body:
        err = body[CONF_ERRORS][0][CONF_MESSAGE]

    return {"title": str(data[CONF_MOBILE]), "data": body, "error": err}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Yodel."""

    VERSION = 1

    def __init__(self):
        """Init."""
        self._mobile = None

    @callback
    def _entry_exists(self):
        """Check if an entry for this domain already exists."""
        existing_entries = self._async_current_entries()
        return len(existing_entries) > 0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial user step."""

        if self._entry_exists():
            return self.async_abort(reason="already_configured")

        errors = {}
        placeholder = ""

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except HomeAssistantError:
                errors["base"] = "cannot_connect"
            else:
                if info["error"] is not None:
                    errors["base"] = "invalid_auth"
                    placeholder = info["error"]
                else:
                    self._mobile = user_input[CONF_MOBILE]
                    return self.async_show_form(
                        step_id="mfa",
                        data_schema=STEP_MFA,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            description_placeholders={CONF_MOBILE: placeholder},
            errors=errors,
        )

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the MFA step."""

        errors = {}
        placeholder = ""

        try:
            user_input[CONF_MOBILE] = self._mobile
            info = await validate_mfa_input(self.hass, user_input)
        except HomeAssistantError:
            errors["base"] = "cannot_connect"
        else:
            if info["error"] is not None:
                errors["base"] = "invalid_auth"
                placeholder = info["error"]
            else:
                data = dict(user_input)

                existing_entries = self.hass.config_entries.async_entries(DOMAIN)

                # Check if an entry already exists with the same username
                existing_entry = next(
                    (
                        entry
                        for entry in existing_entries
                        if entry.data.get(CONF_MOBILE) == user_input[CONF_MOBILE]
                    ),
                    None,
                )

                if existing_entry is not None:
                    # Update specific data in the entry
                    updated_data = existing_entry.data.copy()
                    # Merge the import_data into the entry_data
                    updated_data.update(data)
                    # Update the entry with the new data
                    self.hass.config_entries.async_update_entry(
                        existing_entry, data=updated_data
                    )
                else:
                    data.update(info[CONF_DATA])

                return self.async_create_entry(
                    title=data[CONF_DATA][CONF_VERIFYAPPMOBILENUMBER][CONF_USER][
                        CONF_EMAIL
                    ],
                    data=data,
                )

        return self.async_show_form(
            step_id="mfa",
            data_schema=STEP_MFA,
            description_placeholders={CONF_MOBILE: placeholder},
            errors=errors,
        )

    async def async_step_import(self, import_data=None) -> FlowResult:
        """Handle the import step for the service call."""
        if import_data is not None:
            try:
                entry_data = self.hass.config_entries.async_entries(DOMAIN)[0].data

                for entry in self._async_current_entries():
                    # Update specific data in the entry
                    updated_data = entry.data.copy()
                    # Merge the import_data into the entry_data
                    updated_data.update(entry_data)
                    self.hass.config_entries.async_update_entry(
                        entry, data=updated_data
                    )
                    # Ensure that the config entry is fully set up before attempting a reload
                    if entry.state == ConfigEntryState.LOADED:
                        self.hass.async_create_task(
                            self.hass.config_entries.async_reload(entry.entry_id)
                        )

            except Exception as e:  # pylint: disable=broad-except
                return self.async_abort(reason="import_failed")

        # Explicitly handle the case where import_data is None
        return self.async_abort(reason="no_import_data")
