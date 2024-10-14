"""Yodel sensor platform."""

from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ACCESSTOKEN,
    CONF_DATA,
    CONF_DEVICEID,
    CONF_EMAIL,
    CONF_NICKNAME,
    CONF_OUT_FOR_DELIVERY,
    CONF_PARCELS,
    CONF_REFRESHTOKEN,
    CONF_SCAN_CODE,
    CONF_SCAN_DATETIME,
    CONF_SCAN_DESCRIPTION,
    CONF_STATUSMESSAGE,
    CONF_TOKEN,
    CONF_TRACKINGEVENTS,
    CONF_UPI_CODE,
    CONF_UPICODE,
    CONF_USER,
    CONF_VERIFYAPPMOBILENUMBER,
    CONF_YODELPARCEL,
    DOMAIN,
    PARCEL_DELIVERED,
    PARCEL_DELIVERY_TODAY,
    PARCEL_IN_TRANSIT,
)
from .coordinator import YodelHideParcelCoordinator, YodelParcelsCoordinator


def get_parcel_header_data(data: dict) -> dict:
    """Get parcel header data."""
    access_token = data[CONF_DATA][CONF_VERIFYAPPMOBILENUMBER][CONF_ACCESSTOKEN][
        CONF_TOKEN
    ]
    refresh_token = data[CONF_DATA][CONF_VERIFYAPPMOBILENUMBER][CONF_ACCESSTOKEN][
        CONF_REFRESHTOKEN
    ]
    device_id = data[CONF_DATA][CONF_VERIFYAPPMOBILENUMBER][CONF_DEVICEID]

    return {
        CONF_ACCESSTOKEN: access_token,
        CONF_REFRESHTOKEN: refresh_token,
        CONF_DEVICEID: device_id,
    }


def hasMailPieceExpired(hass: HomeAssistant, expiry_date_raw: str) -> bool:
    """Check if booking has expired."""

    user_timezone = dt_util.get_time_zone(hass.config.time_zone)

    dt_utc = datetime.strptime(expiry_date_raw, "%Y-%m-%dT%H:%M:%S%z").replace(
        tzinfo=user_timezone
    )
    # Convert the datetime to the default timezone
    expiry_date = dt_utc.astimezone(user_timezone)
    return (datetime.today().timestamp() - expiry_date.timestamp()) >= 86400


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry created in the integrations UI."""

    config = hass.data[DOMAIN][entry.entry_id]
    if entry.options:
        config.update(entry.options)

    if entry.data:
        session = async_get_clientsession(hass)

        name = entry.data[CONF_DATA][CONF_VERIFYAPPMOBILENUMBER][CONF_USER][CONF_EMAIL]

        header_data = get_parcel_header_data(entry.data)

        parcelsCoordinator = YodelParcelsCoordinator(hass, session, header_data)

        await parcelsCoordinator.async_config_entry_first_refresh()

        parcels = list(parcelsCoordinator.data.get(CONF_PARCELS))
        sensors = []
        for parcel in parcels:
            lastTrackingEventScanCode = parcel[CONF_TRACKINGEVENTS][0][CONF_SCAN_CODE]
            add_entity = True
            if lastTrackingEventScanCode in PARCEL_DELIVERED:
                delivered_at = parcel[CONF_TRACKINGEVENTS][0][CONF_SCAN_DATETIME]
                if hasMailPieceExpired(hass, delivered_at):
                    add_entity = False

                    data = {CONF_UPI_CODE: parcel[CONF_YODELPARCEL][CONF_UPICODE]}

                    hideParcelCoordinator = YodelHideParcelCoordinator(
                        hass, session, data, header_data
                    )

                    await hideParcelCoordinator.async_refresh()

            if add_entity:
                sensors.append(YodelParcelSensor(hass=hass, data=parcel, name=name))

        await parcelsCoordinator.async_refresh()

        total_sensor = TotalParcelsSensor(parcelsCoordinator, name)

        sensors = [*sensors, total_sensor]
        for sensor in sensors:
            hass.data[DOMAIN][sensor.unique_id] = sensor

        async_add_entities(sensors, update_before_add=True)


async def remove_unavailable_entities(hass: HomeAssistant):
    """Remove entities no longer provided by the integration."""
    # Access the entity registry
    registry = er.async_get(hass)

    # Loop through all registered entities
    for entity_id in list(registry.entities):
        entity = registry.entities[entity_id]
        # Check if the entity belongs to your integration (by checking domain)
        if entity.platform == DOMAIN:
            # Check if the entity is not available in `hass.states`
            state = hass.states.get(entity_id)

            # If the entity's state is unavailable or not in `hass.states`
            if state is None or state.state == "unavailable":
                registry.async_remove(entity_id)


class TotalParcelsSensor(CoordinatorEntity[DataUpdateCoordinator], SensorEntity):
    """Sensor to track the total number of parcels."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        name: str,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.total_parcels = self.coordinator.data[CONF_PARCELS]
        self._state = self.get_state()
        self._name = "Yodel Parcels"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{name}")},
            manufacturer="Yodel",
            model="Parcel Tracker",
            name="Yodel - Parcel Tracker",
            configuration_url="https://github.com/jampez77/Yodel/",
        )
        self._attr_unique_id = f"{DOMAIN}-{name}-tracked_parcels".lower()
        self.entity_id = f"sensor.{DOMAIN}_tracked_parcels".lower()

        self.attrs: dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Name."""
        return self._name

    @property
    def state(self) -> int:
        """State."""
        return self._state

    def get_state(self) -> int:
        """Update the state based on the number of tracked parcels."""
        return len(self.total_parcels)

    @property
    def icon(self) -> str:
        """Set total parcels icon."""
        return "mdi:package-variant-closed"

    def update_from_coordinator(self):
        """Update sensor state and attributes from coordinator data."""
        parcels_out_for_delivery = []

        parcels = self.coordinator.data[CONF_PARCELS]

        self.total_parcels = parcels

        for parcel in parcels:
            lastTrackingEventScanCode = parcel[CONF_TRACKINGEVENTS][0][CONF_SCAN_CODE]

            if lastTrackingEventScanCode in PARCEL_DELIVERY_TODAY:
                parcels_out_for_delivery.append(parcel)

            for entity in self.hass.data[DOMAIN].values():
                if (
                    isinstance(entity, YodelParcelSensor)
                    and str(parcel[CONF_YODELPARCEL][CONF_UPICODE]).lower()
                    in entity.unique_id
                ):
                    entity.update_parcel_data(parcel)

        self.attrs[CONF_PARCELS] = [
            parcel[CONF_YODELPARCEL][CONF_UPICODE] for parcel in parcels
        ]

        self.attrs[CONF_OUT_FOR_DELIVERY] = [
            parcel[CONF_YODELPARCEL][CONF_UPICODE]
            for parcel in parcels_out_for_delivery
        ]

        self._state = self.get_state()

        self.hass.add_job(remove_unavailable_entities(self.hass))

    def is_parcel_delivery_today(self, parcel: dict) -> bool:
        """Check if the parcel has been delivered."""
        tracking_events = parcel.get(CONF_TRACKINGEVENTS, [])
        if tracking_events:
            most_recent_event = tracking_events[0]
            lastTrackingEventScanCode = most_recent_event[CONF_TRACKINGEVENTS][0][
                CONF_SCAN_CODE
            ]
            return lastTrackingEventScanCode in PARCEL_DELIVERY_TODAY
        return False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_from_coordinator()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle adding to Home Assistant."""
        await super().async_added_to_hass()
        await self.async_update()

    async def async_remove(self) -> None:
        """Handle the removal of the entity."""
        # If you have any specific cleanup logic, add it here
        if self.hass is not None:
            await super().async_remove()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Define entity attributes."""
        return self.attrs


class YodelParcelSensor(SensorEntity):
    """Define a Yodel parcel sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        data: dict,
        name: str,
    ) -> None:
        """Initialize."""
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{name}")},
            manufacturer="Yodel",
            model="Parcel Tracker",
            name="Yodel - Parcel Tracker",
            configuration_url="https://github.com/jampez77/Yodel/",
        )
        self.data = data
        self.hass = hass
        parcel_code = self.data[CONF_YODELPARCEL][CONF_UPICODE]
        sensor_id = f"{DOMAIN}_parcel_{parcel_code}".lower()
        # Set the unique ID based on domain, name, and sensor type
        self._attr_unique_id = f"{DOMAIN}-{name}-{parcel_code}".lower()
        self.entity_id = f"sensor.{DOMAIN}_parcel_{parcel_code}".lower()
        self.entity_description = SensorEntityDescription(
            key=f"yodel_{parcel_code}",
            name=parcel_code,
            icon="mdi:package-variant-closed-check",
        )
        self._name = self.update_name()
        self._sensor_id = sensor_id
        self.attrs = self.update_attributes()
        self._available = self.update_available()
        self._attr_icon = self.update_icon()
        self._state = self.update_state()

    async def async_remove(self) -> None:
        """Handle the removal of the entity."""
        # If you have any specific cleanup logic, add it here
        if self.hass is not None:
            await super().async_remove()

    def update_name(self) -> str:
        """Update name."""
        if self.data[CONF_YODELPARCEL][CONF_NICKNAME] is not None:
            return self.data[CONF_YODELPARCEL][CONF_NICKNAME]

        return self.data[CONF_YODELPARCEL][CONF_UPICODE]

    def update_available(self) -> bool:
        """Update available."""
        return self.data is not None

    def update_icon(self) -> str:
        """Update Icon."""
        if CONF_TRACKINGEVENTS in self.data and len(self.data[CONF_TRACKINGEVENTS]) > 0:
            lastTrackingEventScanCode = self.data[CONF_TRACKINGEVENTS][0][
                CONF_SCAN_CODE
            ]

            if lastTrackingEventScanCode in PARCEL_DELIVERED:
                return "mdi:package-variant-closed-check"
            if lastTrackingEventScanCode in PARCEL_DELIVERY_TODAY:
                return "mdi:truck-delivery-outline"
            if lastTrackingEventScanCode in PARCEL_IN_TRANSIT:
                return "mdi:transit-connection-variant"

        return "mdi:package-variant-closed"

    def update_state(self) -> str:
        """Update State."""

        value = self.data[CONF_YODELPARCEL][CONF_STATUSMESSAGE]

        if CONF_TRACKINGEVENTS in self.data and len(self.data[CONF_TRACKINGEVENTS]) > 0:
            lastTrackingEventScanCode = self.data[CONF_TRACKINGEVENTS][0][
                CONF_SCAN_CODE
            ]
            if lastTrackingEventScanCode not in PARCEL_DELIVERED:
                value = self.data[CONF_TRACKINGEVENTS][0][CONF_SCAN_DESCRIPTION]

        return value

    def update_attributes(self) -> dict[str, Any]:
        """Update Attributes."""
        attributes = {}

        for key, value in self.data.items():
            if isinstance(value, dict):
                attributes.update({f"{key}_{k}": v for k, v in value.items()})
            else:
                attributes[key] = value

        return attributes

    def update_parcel_data(self, data):
        """Update parcel data."""
        self.data = data
        self._name = self.update_name()
        self._available = self.update_available()
        self._attr_icon = self.update_icon()
        self._state = self.update_state()
        self.attrs = self.update_attributes()

        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Process name."""
        return self.update_name()

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self.update_available()

    @property
    def icon(self) -> str:
        """Return a representative icon of the parcel."""
        return self.update_icon()

    @property
    def native_value(self) -> str | date | None:
        """Native value."""
        return self.update_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Define entity attributes."""
        return self.update_attributes()
