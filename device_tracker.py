from config.custom_components.gabb.client import GabbClient

import json
import voluptuous as vol
from homeassistant.helpers.event import (
    async_track_device_registry_updated_event,
)
from homeassistant.config_entries import ConfigEntry
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.device_tracker import (
    TrackerEntity,
    PLATFORM_SCHEMA,
    AsyncSeeCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from datetime import timedelta

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME, default="admin"): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


SCAN_INTERVAL = timedelta(seconds=60)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Gabb Tracker platform."""
    # Assign configuration variables.
    # The configuration check takes care they are present.
    host = config[CONF_HOST]
    username = config[CONF_USERNAME]
    password = config.get(CONF_PASSWORD)

    # Setup connection with devices/cloud
    # hub = awesomelights.Hub(host, username, password)
    gc = GabbClient(username, password, host)
    map = gc.get_map()
    result = json.loads(map.content)
    # Verify that passed in configuration works
    # if not hub.is_valid_login():
    #   _LOGGER.error("Could not connect to AwesomeLight hub")
    #     return

    # Add devices
    add_entities(
        GabbTracker(gabb_device, config, hass)
        for gabb_device in result["data"]["Devices"]
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Gabb Tracker platform."""
    # Assign configuration variables.
    # The configuration check takes care they are present.
    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    # Setup connection with devices/cloud
    # hub = awesomelights.Hub(host, username, password)
    gc = await hass.async_add_executor_job(
        GabbClient,
        username,
        password,
        host,
    )

    map = await hass.async_add_executor_job(gc.get_map)

    result = json.loads(map.content)
    # Verify that passed in configuration works
    # if not hub.is_valid_login():
    #   _LOGGER.error("Could not connect to AwesomeLight hub")
    #     return

    # Add devices
    async_add_entities(
        GabbTracker(gabb_device, entry.data, hass)
        for gabb_device in result["data"]["Devices"]
    )


class GabbTracker(TrackerEntity):
    """Gabb Tracker to determine location of gabb watch"""

    my_lat = 0.0
    my_long = 0.0
    my_name = ""
    my_id = ""
    my_battery_level = 0
    my_config = {CONF_HOST: "", CONF_USERNAME: "", CONF_PASSWORD: ""}
    my_hass: HomeAssistant

    def __init__(self, gabb_device, cnfg, hass) -> None:
        """Initialize a Gabb Tracker"""
        self.my_id = gabb_device["id"]
        self.my_config = cnfg
        self._attr_unique_id = f"gabb--{self.my_id}"
        self.my_hass = hass
        self._device_id = self._attr_unique_id
        self.initialize_device(gabb_device)

    def initialize_device(self, gabb_device) -> None:
        self.my_lat = gabb_device["latitude"]
        self.my_long = gabb_device["longitude"]
        self.my_battery_level = gabb_device["batteryLevel"]
        self._attr_name = (
            gabb_device["firstName"]
            + " "
            + gabb_device["lastName"]
            + " ("
            + gabb_device["gsmNumber"]
            + ")"
        )

    @property
    def latitude(self) -> float | None:
        return self.my_lat

    @property
    def longitude(self) -> float | None:
        return self.my_long

    @property
    def battery_level(self) -> int | None:
        return self.my_battery_level

    @property
    def source_type(self) -> str | None:
        return "gps"

    @property
    def should_poll(self) -> bool | None:
        return True

    @callback
    def _async_subscribe_device_updates(self) -> None:
        """Subscribe to device registry updates."""
        assert self.registry_entry

        self._async_unsubscribe_device_updates()

        self._unsub_device_updates = async_track_device_registry_updated_event(
            self.hass,
            [self.my_id],
            self._async_device_registry_updated,
        )

    def update(self) -> None:
        host = self.my_config[CONF_HOST]
        username = self.my_config[CONF_USERNAME]
        password = self.my_config[CONF_PASSWORD]
        gc = GabbClient(username, password, host)
        map = gc.get_map()
        result = json.loads(map.content)
        for x in result["data"]["Devices"]:
            if x["id"] == self.my_id:
                self.initialize_device(x)

    async def async_update(self) -> None:
        """Update entity."""
        gc = await self.my_hass.async_add_executor_job(
            GabbClient,
            self.my_config[CONF_USERNAME],
            self.my_config[CONF_PASSWORD],
            self.my_config[CONF_HOST],
        )
        map = await self.my_hass.async_add_executor_job(gc.get_map)
        result = json.loads(map.content)
        for x in result["data"]["Devices"]:
            if x["id"] == self.my_id:
                self.initialize_device(x)
