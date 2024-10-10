"""Ryanair Coordinator."""

from datetime import timedelta
import hashlib
import logging
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CAPTURE_MOBILE_POST_BODY,
    CONF_ACCESSTOKEN,
    CONF_AUTHORIZATION,
    CONF_CONSIGNMENTORUPICODE,
    CONF_DATA,
    CONF_DEVICEID,
    CONF_MFA_CODE,
    CONF_MOBILE,
    CONF_NICKNAME,
    CONF_PARCELS,
    CONF_POST,
    CONF_POSTCODE,
    CONF_REFRESH_TOKEN,
    CONF_REFRESHTOKEN,
    CONF_TOKEN,
    CONF_TRACKPARCEL,
    CONF_UPI_CODE,
    CONF_UPICODE,
    CONF_VARIABLES,
    CONF_YODEL_DEVICE_ID,
    CONF_YODELPARCEL,
    HOST,
    NAME_PARCEL_POST_BODY,
    PARCELS_POST_BODY,
    REQUEST_HEADER,
    REQUEST_HEADER_API_KEY,
    TRACK_PARCEL_POST_BODY,
    VERIFY_MOBILE_POST_BODY,
)

_LOGGER = logging.getLogger(__name__)


def generate_device_fingerprint(mobile: str) -> str:
    """Generate device fingerprint."""

    unique_id = hashlib.md5(mobile.encode("UTF-8")).hexdigest()
    return str(uuid.UUID(hex=unique_id))


class YodelParcelsCoordinator(DataUpdateCoordinator):
    """Parcels coordinator."""

    def __init__(self, hass: HomeAssistant, session, header_data) -> None:
        """Initialize coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Yodel",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(minutes=5),
        )

        self.session = session
        self.hass = hass
        self.access_token = header_data[CONF_ACCESSTOKEN]
        self.refresh_token = header_data[CONF_REFRESHTOKEN]
        self.device_id = header_data[CONF_DEVICEID]
        self.header_data = header_data

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        body = {}
        body[CONF_PARCELS] = []
        try:
            REQUEST_HEADER[CONF_AUTHORIZATION] = f"Bearer {self.access_token}"
            REQUEST_HEADER[CONF_REFRESH_TOKEN] = self.refresh_token
            REQUEST_HEADER[CONF_YODEL_DEVICE_ID] = self.device_id

            parcelsResp = await self.session.request(
                method=CONF_POST,
                url=HOST,
                headers=REQUEST_HEADER,
                json=PARCELS_POST_BODY,
            )

            parcels = await parcelsResp.json()

            parcels = parcels[CONF_DATA][CONF_PARCELS]

            for parcel in parcels:
                data = {
                    CONF_UPI_CODE: parcel[CONF_YODELPARCEL][CONF_UPICODE],
                    CONF_POSTCODE: parcel[CONF_YODELPARCEL][CONF_POSTCODE],
                }

                parcelCoordinator = YodelTrackParcelCoordinator(
                    self.hass, self.session, data, self.header_data
                )

                await parcelCoordinator.async_refresh()

                parcel_data = parcelCoordinator.data.get(CONF_DATA)[CONF_TRACKPARCEL]

                body[CONF_PARCELS].append(parcel_data)

        except InvalidAuth as err:
            raise ConfigEntryAuthFailed from err
        except YodelError as err:
            raise UpdateFailed(str(err)) from err
        except ValueError as err:
            _LOGGER.error("Value error occurred: %s", err)
            raise UpdateFailed(f"Unexpected response: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected exception: %s", err)
            raise UnknownError from err
        else:
            return body


class YodelTrackParcelCoordinator(DataUpdateCoordinator):
    """Parcels coordinator."""

    def __init__(self, hass: HomeAssistant, session, data, header_data) -> None:
        """Initialize coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Yodel",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=None,
        )

        self.session = session
        self.upi_code = data[CONF_UPI_CODE]
        self.postcode = data[CONF_POSTCODE]

        self.access_token = header_data[CONF_ACCESSTOKEN]
        self.refresh_token = header_data[CONF_REFRESHTOKEN]
        self.device_id = header_data[CONF_DEVICEID]

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            REQUEST_HEADER[CONF_AUTHORIZATION] = f"Bearer {self.access_token}"
            REQUEST_HEADER[CONF_REFRESH_TOKEN] = self.refresh_token
            REQUEST_HEADER[CONF_YODEL_DEVICE_ID] = self.device_id

            TRACK_PARCEL_POST_BODY[CONF_VARIABLES][CONF_CONSIGNMENTORUPICODE] = (
                self.upi_code
            )
            TRACK_PARCEL_POST_BODY[CONF_VARIABLES][CONF_POSTCODE] = self.postcode

            resp = await self.session.request(
                method=CONF_POST,
                url=HOST,
                headers=REQUEST_HEADER,
                json=TRACK_PARCEL_POST_BODY,
            )

            body = await resp.json()

        except InvalidAuth as err:
            raise ConfigEntryAuthFailed from err
        except YodelError as err:
            raise UpdateFailed(str(err)) from err
        except ValueError as err:
            _LOGGER.error("Value error occurred: %s", err)
            raise UpdateFailed(f"Unexpected response: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected exception: %s", err)
            raise UnknownError from err
        else:
            return body


class YodelMfaCoordinator(DataUpdateCoordinator):
    """MFA coordinator."""

    def __init__(self, hass: HomeAssistant, session, data) -> None:
        """Initialize coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Yodel",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=None,
        )

        self.session = session
        self.mfa_code = data[CONF_MFA_CODE]
        self.fingerprint = generate_device_fingerprint(data[CONF_MOBILE])

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            VERIFY_MOBILE_POST_BODY[CONF_VARIABLES][CONF_DEVICEID] = self.fingerprint
            VERIFY_MOBILE_POST_BODY[CONF_VARIABLES][CONF_TOKEN] = self.mfa_code

            resp = await self.session.request(
                method=CONF_POST,
                url=HOST,
                headers=REQUEST_HEADER_API_KEY,
                json=VERIFY_MOBILE_POST_BODY,
            )

            body = await resp.json()

        except InvalidAuth as err:
            raise ConfigEntryAuthFailed from err
        except YodelError as err:
            raise UpdateFailed(str(err)) from err
        except ValueError as err:
            _LOGGER.error("Value error occurred: %s", err)
            raise UpdateFailed(f"Unexpected response: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected exception: %s", err)
            raise UnknownError from err
        else:
            return body


class YodelAuthenticationCoordinator(DataUpdateCoordinator):
    """Authentication coordinator."""

    def __init__(self, hass: HomeAssistant, session, data) -> None:
        """Initialize coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Yodel",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=None,
        )

        self.session = session
        self.mobile = data[CONF_MOBILE]
        self.fingerprint = generate_device_fingerprint(self.mobile)

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            CAPTURE_MOBILE_POST_BODY[CONF_VARIABLES][CONF_DEVICEID] = self.fingerprint
            CAPTURE_MOBILE_POST_BODY[CONF_VARIABLES][CONF_MOBILE] = self.mobile

            resp = await self.session.request(
                method=CONF_POST,
                url=HOST,
                headers=REQUEST_HEADER_API_KEY,
                json=CAPTURE_MOBILE_POST_BODY,
            )

            body = await resp.json()

        except InvalidAuth as err:
            raise ConfigEntryAuthFailed from err
        except YodelError as err:
            raise UpdateFailed(str(err)) from err
        except ValueError as err:
            _LOGGER.error("Value error occurred: %s", err)
            raise UpdateFailed(f"Unexpected response: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected exception: %s", err)
            raise UnknownError from err
        else:
            return body


class YodelParcelNameCoordinator(DataUpdateCoordinator):
    """Authentication coordinator."""

    def __init__(self, hass: HomeAssistant, session, data, header_data) -> None:
        """Initialize coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Yodel",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=None,
        )

        self.session = session
        self.upi_code = data[CONF_UPI_CODE]
        self.nickname = data[CONF_NICKNAME]

        self.access_token = header_data[CONF_ACCESSTOKEN]
        self.refresh_token = header_data[CONF_REFRESHTOKEN]
        self.device_id = header_data[CONF_DEVICEID]

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            NAME_PARCEL_POST_BODY[CONF_VARIABLES][CONF_UPICODE] = self.upi_code
            NAME_PARCEL_POST_BODY[CONF_VARIABLES][CONF_NICKNAME] = self.nickname

            REQUEST_HEADER[CONF_AUTHORIZATION] = f"Bearer {self.access_token}"
            REQUEST_HEADER[CONF_REFRESH_TOKEN] = self.refresh_token
            REQUEST_HEADER[CONF_YODEL_DEVICE_ID] = self.device_id

            resp = await self.session.request(
                method=CONF_POST,
                url=HOST,
                headers=REQUEST_HEADER,
                json=NAME_PARCEL_POST_BODY,
            )

            body = await resp.json()

        except InvalidAuth as err:
            raise ConfigEntryAuthFailed from err
        except YodelError as err:
            raise UpdateFailed(str(err)) from err
        except ValueError as err:
            _LOGGER.error("Value error occurred: %s", err)
            raise UpdateFailed(f"Unexpected response: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected exception: %s", err)
            raise UnknownError from err
        else:
            return body


class YodelError(HomeAssistantError):
    """Base error."""


class InvalidAuth(YodelError):
    """Raised when invalid authentication credentials are provided."""


class APIRatelimitExceeded(YodelError):
    """Raised when the API rate limit is exceeded."""


class UnknownError(YodelError):
    """Raised when an unknown error occurs."""
