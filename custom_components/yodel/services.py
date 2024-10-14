"""Services for Yodel integration."""

import functools

import voluptuous as vol

from homeassistant.components.persistent_notification import (
    async_create as create_notification,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ACCESSTOKEN,
    CONF_DATA,
    CONF_DEVICEID,
    CONF_ERRORS,
    CONF_MESSAGE,
    CONF_NAME_A_PARCEL,
    CONF_NICKNAME,
    CONF_POSTCODE,
    CONF_REFRESHTOKEN,
    CONF_TOKEN,
    CONF_TRACK_A_PARCEL,
    CONF_UPI_CODE,
    CONF_VERIFYAPPMOBILENUMBER,
    DOMAIN,
)
from .coordinator import YodelParcelNameCoordinator, YodelTrackParcelCoordinator
from .sensor import YodelParcelSensor

NAME_PARCEL_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_UPI_CODE): cv.string,
        vol.Required(CONF_NICKNAME): cv.string,
    }
)

TRACK_PARCEL_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_UPI_CODE): cv.string,
        vol.Required(CONF_POSTCODE): cv.string,
    }
)


def async_cleanup_services(hass: HomeAssistant) -> None:
    """Cleanup Yodel services."""
    hass.services.async_remove(DOMAIN, CONF_NAME_A_PARCEL)
    hass.services.async_remove(DOMAIN, CONF_TRACK_A_PARCEL)


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Royal Mail services."""
    services = [
        (
            CONF_TRACK_A_PARCEL,
            functools.partial(track_a_parcel, hass),
            TRACK_PARCEL_SERVICE_SCHEMA,
        ),
        (
            CONF_NAME_A_PARCEL,
            functools.partial(name_a_parcel, hass),
            NAME_PARCEL_SERVICE_SCHEMA,
        ),
    ]
    for name, method, schema in services:
        if hass.services.has_service(DOMAIN, name):
            continue
        hass.services.async_register(DOMAIN, name, method, schema=schema)


async def track_a_parcel(hass: HomeAssistant, call: ServiceCall) -> None:
    """Track a parcel."""

    entry_data = hass.config_entries.async_entries(DOMAIN)[0].data

    upi_code = call.data[CONF_UPI_CODE]

    access_token = entry_data[CONF_DATA][CONF_VERIFYAPPMOBILENUMBER][CONF_ACCESSTOKEN][
        CONF_TOKEN
    ]
    refresh_token = entry_data[CONF_DATA][CONF_VERIFYAPPMOBILENUMBER][CONF_ACCESSTOKEN][
        CONF_REFRESHTOKEN
    ]
    device_id = entry_data[CONF_DATA][CONF_VERIFYAPPMOBILENUMBER][CONF_DEVICEID]

    header_data = {
        CONF_ACCESSTOKEN: access_token,
        CONF_REFRESHTOKEN: refresh_token,
        CONF_DEVICEID: device_id,
    }

    session = async_get_clientsession(hass)

    parcelCoordinator = YodelTrackParcelCoordinator(
        hass, session, call.data, header_data
    )

    await parcelCoordinator.async_request_refresh()

    if parcelCoordinator.last_exception is not None:
        return False

    data = parcelCoordinator.data

    err = None
    if CONF_ERRORS in data:
        err = data[CONF_ERRORS][0][CONF_MESSAGE]
        raise HomeAssistantError(
            f"Yodel returned response ({err}) for tracking number {upi_code}"
        )

    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "import"},
        data=call.data,
    )
    return True


async def name_a_parcel(hass: HomeAssistant, call: ServiceCall) -> None:
    """Name a parcel."""

    upi_code = call.data[CONF_UPI_CODE]
    nickname = call.data[CONF_NICKNAME]

    entry_data = hass.config_entries.async_entries(DOMAIN)[0].data

    session = async_get_clientsession(hass)

    access_token = entry_data[CONF_DATA][CONF_VERIFYAPPMOBILENUMBER][CONF_ACCESSTOKEN][
        CONF_TOKEN
    ]
    refresh_token = entry_data[CONF_DATA][CONF_VERIFYAPPMOBILENUMBER][CONF_ACCESSTOKEN][
        CONF_REFRESHTOKEN
    ]
    device_id = entry_data[CONF_DATA][CONF_VERIFYAPPMOBILENUMBER][CONF_DEVICEID]

    header_data = {
        CONF_ACCESSTOKEN: access_token,
        CONF_REFRESHTOKEN: refresh_token,
        CONF_DEVICEID: device_id,
    }

    coordinator = YodelParcelNameCoordinator(hass, session, call.data, header_data)

    await coordinator.async_request_refresh()

    if coordinator.last_exception is not None:
        return create_notification(
            hass,
            f"There was an issue updating the name for parcel {upi_code}",
            title="Unable to update Yodel parcel name",
            notification_id=f"yodel_name_parcel_{upi_code}_failure",
        )

    create_notification(
        hass,
        f"Yodel Parcel {upi_code} name updated to {nickname}",
        title="Updated Yodel parcel name",
        notification_id=f"yodel_name_parcel_{upi_code}_success",
    )

    for entity_id in hass.data.get(DOMAIN, {}):
        if str(upi_code).lower() in entity_id:
            entity = hass.data[DOMAIN].get(entity_id)
            if isinstance(entity, YodelParcelSensor):
                await entity.update_parcel_data(coordinator.data)
                break

    return True
