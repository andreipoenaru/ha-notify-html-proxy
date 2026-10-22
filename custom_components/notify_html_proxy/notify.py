"""Notify platform that converts plain-text messages to HTML and forwards them."""

from __future__ import annotations

import html
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "notify_html_proxy"
CONF_TARGET_SERVICE = "target_service"


def _target_service_name(value: Any) -> str:
    """Accept both ``my_service`` and ``notify.my_service``."""
    name = cv.string(value).strip()
    prefix = f"{NOTIFY_DOMAIN}."
    if name.startswith(prefix):
        name = name[len(prefix) :]
    return cv.slug(name)


PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_TARGET_SERVICE): _target_service_name}
)


def plain_to_html(message: str) -> str:
    """Escape ``message`` and turn newlines into ``<br>`` tags.

    Escaping happens first so that the inserted ``<br>`` tags survive.
    """
    normalized = message.replace("\r\n", "\n").replace("\r", "\n")
    return html.escape(normalized, quote=False).replace("\n", "<br>\n")


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> HtmlProxyNotificationService:
    """Get the notification service."""
    target: str = config[CONF_TARGET_SERVICE]
    own_name: str = config.get(CONF_NAME) or DOMAIN
    if target == own_name:
        raise ValueError(
            f"{DOMAIN}: target_service must not be the proxy itself ('{own_name}')"
        )
    return HtmlProxyNotificationService(hass, target)


class HtmlProxyNotificationService(BaseNotificationService):
    """Forward notifications to another notify service with an HTML message."""

    def __init__(self, hass: HomeAssistant, target_service: str) -> None:
        """Initialize the service."""
        self.hass = hass
        self._target_service = target_service

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Convert the message to HTML and forward the call unchanged otherwise."""
        # The target is resolved lazily: the downstream integration may not have
        # registered its service yet when this platform is set up.
        if not self.hass.services.has_service(NOTIFY_DOMAIN, self._target_service):
            error = (
                f"Target notify service '{NOTIFY_DOMAIN}.{self._target_service}' "
                "does not exist"
            )
            # Also log: notify groups may swallow exceptions of their members.
            _LOGGER.error(error)
            raise ServiceValidationError(error)

        payload: dict[str, Any] = {"message": plain_to_html(message)}
        for key in (ATTR_TITLE, ATTR_TARGET, ATTR_DATA):
            if (value := kwargs.get(key)) is not None:
                payload[key] = value

        await self.hass.services.async_call(
            NOTIFY_DOMAIN, self._target_service, payload, blocking=True
        )
