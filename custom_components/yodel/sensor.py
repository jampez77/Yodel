"""Yodel sensor platform."""

from datetime import date
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

from .const import (
    CONF_ACCESSTOKEN,
    CONF_DATA,
    CONF_DEVICEID,
    CONF_EMAIL,
    CONF_NICKNAME,
    CONF_OUT_FOR_DELIVERY,
    CONF_PARCELS,
    CONF_POSTCODE,
    CONF_REFRESHTOKEN,
    CONF_SCAN_CODE,
    CONF_STATUSMESSAGE,
    CONF_TOKEN,
    CONF_TRACKINGEVENTS,
    CONF_TRACKPARCEL,
    CONF_UPI_CODE,
    CONF_UPICODE,
    CONF_USER,
    CONF_VERIFYAPPMOBILENUMBER,
    CONF_YODELPARCEL,
    DELIVERY_DELIVERED_EVENTS,
    DELIVERY_TODAY_EVENTS,
    DELIVERY_TRANSIT_EVENTS,
    DOMAIN,
)
from .coordinator import YodelParcelsCoordinator, YodelTrackParcelCoordinator


async def remove_unmanaged_entities(hass: HomeAssistant):
    """Remove entities from Home Assistant that are no longer managed by the integration."""
    # Get the entity registry
    entity_registry = er.async_get(hass)

    # Get the list of currently managed entities
    managed_entities = hass.data.get(DOMAIN, {}).get("managed_entities", set())

    # List to store IDs of entities to be removed
    entities_to_remove = []

    # Iterate over all entities in the registry
    for entity_id, entry in entity_registry.entities.items():
        # Check if the entity belongs to the specified integration and is not managed
        if entry.platform == DOMAIN and entity_id not in managed_entities:
            entities_to_remove.append(entity_id)

    # Remove the orphaned entities
    for entity_id in entities_to_remove:
        entity_registry.async_remove(entity_id)


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

        access_token = entry.data[CONF_DATA][CONF_VERIFYAPPMOBILENUMBER][
            CONF_ACCESSTOKEN
        ][CONF_TOKEN]
        refresh_token = entry.data[CONF_DATA][CONF_VERIFYAPPMOBILENUMBER][
            CONF_ACCESSTOKEN
        ][CONF_REFRESHTOKEN]
        device_id = entry.data[CONF_DATA][CONF_VERIFYAPPMOBILENUMBER][CONF_DEVICEID]

        header_data = {
            CONF_ACCESSTOKEN: access_token,
            CONF_REFRESHTOKEN: refresh_token,
            CONF_DEVICEID: device_id,
        }

        parcelsCoordinator = YodelParcelsCoordinator(hass, session, header_data)

        await parcelsCoordinator.async_config_entry_first_refresh()

        parcels = parcelsCoordinator.data
        parcels_out_for_delivery = []
        sensors = []
        parcels = parcels[CONF_DATA][CONF_PARCELS]

        for parcel in parcels:
            data = {
                CONF_UPI_CODE: parcel[CONF_YODELPARCEL][CONF_UPICODE],
                CONF_POSTCODE: parcel[CONF_YODELPARCEL][CONF_POSTCODE],
            }

            parcelCoordinator = YodelTrackParcelCoordinator(
                hass, session, data, header_data
            )

            await parcelCoordinator.async_config_entry_first_refresh()

            parcel_data = parcelCoordinator.data.get(CONF_DATA)[CONF_TRACKPARCEL]

            lastTrackingEventScanCode = parcel_data[CONF_TRACKINGEVENTS][0][
                CONF_SCAN_CODE
            ]

            if lastTrackingEventScanCode in DELIVERY_TODAY_EVENTS:
                parcels_out_for_delivery.append(parcel)

            sensors.append(
                YodelParcelSensor(
                    coordinator=parcelCoordinator,
                    name=name,
                )
            )

        total_sensor = TotalParcelsSensor(hass, name, parcels, parcels_out_for_delivery)

        sensors = [*sensors, total_sensor]
        for sensor in sensors:
            hass.data[DOMAIN][sensor.unique_id] = sensor

        async_add_entities(sensors, update_before_add=True)

        await remove_unavailable_entities(hass)


async def remove_unavailable_entities(hass):
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


class TotalParcelsSensor(SensorEntity):
    """Sensor to track the total number of parcels."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        parcels: list,
        parcels_out_for_delivery: list,
    ):
        """Init."""
        self.total_parcels = parcels
        self.parcels_out_for_delivery = parcels_out_for_delivery
        self._state = len(self.total_parcels)
        self._name = "Tracked Parcels"
        self.hass = hass
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
    def name(self):
        """Name."""
        return self._name

    @property
    def state(self):
        """State."""
        return self._state

    def update_state(self):
        """Update the state based on the number of tracked parcels."""
        self._state = len(self.total_parcels)

    @property
    def icon(self) -> str:
        """Set total parcels icon."""
        return "mdi:package-variant-closed"

    def update_parcels(self, parcels: list, parcels_out_for_delivery: list):
        """Update parcels and re-calculate state."""
        self.total_parcels = parcels
        self.parcels_out_for_delivery = parcels_out_for_delivery
        self.update_state()
        self.async_write_ha_state()

    async def async_remove(self) -> None:
        """Handle the removal of the entity."""
        # If you have any specific cleanup logic, add it here
        await super().async_remove()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Define entity attributes."""

        self.attrs[CONF_PARCELS] = [
            parcel[CONF_YODELPARCEL][CONF_UPICODE] for parcel in self.total_parcels
        ]

        self.attrs[CONF_OUT_FOR_DELIVERY] = [
            parcel[CONF_YODELPARCEL][CONF_UPICODE]
            for parcel in self.parcels_out_for_delivery
        ]

        return self.attrs


class YodelParcelSensor(CoordinatorEntity[DataUpdateCoordinator], SensorEntity):
    """Define a Yodel parcel sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{name}")},
            manufacturer="Yodel",
            model="Parcel Tracker",
            name="Yodel - Parcel Tracker",
            configuration_url="https://github.com/jampez77/Yodel/",
        )
        self.data = coordinator.data.get(CONF_DATA)[CONF_TRACKPARCEL]
        parcel_code = self.data[CONF_YODELPARCEL][CONF_UPICODE]
        sensor_id = f"{DOMAIN}_{parcel_code}".lower()
        # Set the unique ID based on domain, name, and sensor type
        self._attr_unique_id = f"{DOMAIN}-{name}-{parcel_code}".lower()
        self.entity_id = f"sensor.yodel_{parcel_code}".lower()
        self.entity_description = SensorEntityDescription(
            key=f"yodel_{parcel_code}",
            name=parcel_code,
            icon="mdi:package-variant-closed-check",
        )
        self._name = name
        self._sensor_id = sensor_id
        self.attrs: dict[str, Any] = {}
        self._available = True
        self._attr_force_update = True

    @property
    def name(self) -> str:
        """Process name."""

        if self.data[CONF_YODELPARCEL][CONF_NICKNAME] is not None:
            return self.data[CONF_YODELPARCEL][CONF_NICKNAME]

        return super().name

    async def update_parcel(self) -> None:
        """Safely update the name of the entity."""
        await self.coordinator.async_request_refresh()

        super()._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.data = self.coordinator.data.get(CONF_DATA)[CONF_TRACKPARCEL]

        if self.data[CONF_YODELPARCEL][CONF_NICKNAME] is not None:
            self._attr_name = self.data[CONF_YODELPARCEL][CONF_NICKNAME]

        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self.coordinator.last_update_success and self.data is not None

    @property
    def icon(self) -> str:
        """Return a representative icon of the timer."""
        if CONF_TRACKINGEVENTS in self.data and len(self.data[CONF_TRACKINGEVENTS]) > 0:
            lastTrackingEventScanCode = self.data[CONF_TRACKINGEVENTS][0][
                CONF_SCAN_CODE
            ]
            if lastTrackingEventScanCode in DELIVERY_DELIVERED_EVENTS:
                return "mdi:package-variant-closed-check"
            if lastTrackingEventScanCode in DELIVERY_TODAY_EVENTS:
                return "mdi:truck-delivery-outline"
            if lastTrackingEventScanCode in DELIVERY_TRANSIT_EVENTS:
                return "mdi:transit-connection-variant"
        return "mdi:package-variant-closed"

    @property
    def native_value(self) -> str | date | None:
        """Native value."""
        return self.data[CONF_YODELPARCEL][CONF_STATUSMESSAGE]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Define entity attributes."""
        attributes = {}

        for key, value in self.data.items():
            if isinstance(value, dict):
                attributes.update({f"{key}_{k}": v for k, v in value.items()})
            else:
                attributes[key] = value

        return attributes
