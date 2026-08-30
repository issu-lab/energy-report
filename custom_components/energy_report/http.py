"""Authenticated CSV export endpoint for Energy Report."""

from __future__ import annotations

from aiohttp import web

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.util import dt as dt_util

from .const import DOMAIN


class EnergyReportExportView(HomeAssistantView):
    """Download a portable annual backup for one config entry."""

    url = "/api/energy_report/export/{entry_id}/{year}"
    name = "api:energy_report:export"
    requires_auth = True

    async def get(self, request: web.Request, entry_id: str, year: str) -> web.StreamResponse:
        hass = request.app[KEY_HASS]
        controller = hass.data.get(DOMAIN, {}).get(entry_id)
        if controller is None:
            raise web.HTTPNotFound()
        try:
            selected_year = int(year)
        except ValueError as err:
            raise web.HTTPNotFound() from err
        now = dt_util.now()
        if selected_year not in {now.year, now.year - 1}:
            raise web.HTTPNotFound()
        path = await controller.async_export_year(selected_year)
        return web.FileResponse(
            path,
            headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
        )
