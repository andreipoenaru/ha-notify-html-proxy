"""Notify platform that converts plain-text messages to HTML and forwards them."""

from __future__ import annotations

import html
import logging
import re
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

TAB_SIZE = 4
# Leading spaces of a line, or any run of two or more spaces.
_SPACES = re.compile(r"^ +| {2,}")


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


def _preserve_spaces(match: re.Match[str]) -> str:
    """Replace spaces that HTML would collapse with non-breaking spaces.

    Leading spaces are all replaced. Inside a line, the last space of a run is
    kept as a regular space so that long lines can still wrap.
    """
    run = match.group()
    if match.start() == 0:
        return "&nbsp;" * len(run)
    return "&nbsp;" * (len(run) - 1) + " "


def plain_to_html(message: str) -> str:
    """Convert a plain-text message to HTML, preserving its whitespace.

    Tabs are expanded, the text is escaped, runs of spaces and indentation are
    preserved with ``&nbsp;``, and newlines become ``<br>``. Escaping happens
    first so that the inserted markup survives.
    """
    normalized = (
        message.replace("\r\n", "\n").replace("\r", "\n").expandtabs(TAB_SIZE)
    )
    escaped = html.escape(normalized, quote=False)
    return "<br>\n".join(
        _SPACES.sub(_preserve_spaces, line) for line in escaped.split("\n")
    )


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
