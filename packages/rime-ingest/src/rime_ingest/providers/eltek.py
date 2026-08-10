"""Support for Eltek Gateway GPRS Server CSV exports (append-only files).

The Eltek Gateway GPRS Server (often just “GPRS Server”) is a relatively old
Windows utility shipped with GenII receiver loggers (SRV250 / SRV450 and
related). Loggers push readings over mobile data to a host running the
Gateway; the software writes one Windows CSV (or Eltek DAT) file per logger
under a configured directory. This provider does not talk to the logger or
the Gateway process — it polls those CSV files via :class:`EOFFileWatcher`.

The Gateway’s CSV layout is stable but not formally versioned; treat timezone,
channel headers, and sentinel “no data” strings as deployment-specific.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from rime_ingest.transformers.messages import (
    DecapsulatedMessage,
    IdentifiedTimeSeriesPayload,
    IrregularTimeAxis,
)
from rime_ingest.transformers.types import SensorUUID

from ..transport.poll.fs import EOFFileWatcher

_TS = "%d/%m/%Y %H:%M:%S"
_HEADER_KEYS = frozenset({"chan", "unit", "ID", "TX Serial Number", "TX Channel"})


class EltekGPRSServerProvider(EOFFileWatcher):
    """Poll Eltek GPRS Server CSV output → one time-series message per channel Sensor.

    `channel_sensor_map` maps vendor channel ids (e.g. ``Ch-013``) to STA Sensor
    UUIDs (e.g. ``K02212-12943-Ch-013``). Quantity routing is model-tier
    (parser / normalizer for each Sensor's ``SupportedSensors`` value); this
    provider only strips CSV framing and attaches Thing / Sensor identity.
    """

    def __init__(
        self,
        app_name: str,
        *,
        file_path,
        poll_interval: float = 300,
        iana_timezone: str,
        channel_sensor_map: dict[str, str],
        max_retries: int = 10,
    ):
        super().__init__(
            app_name,
            file_path=file_path,
            poll_interval=poll_interval,
            max_retries=max_retries,
        )
        self._headers: dict[str, Any] = defaultdict(str)
        self._header_loaded = False
        self._channel_sensor_map: dict[str, SensorUUID] = dict(channel_sensor_map)
        try:
            self._timezone = ZoneInfo(iana_timezone)
        except Exception as e:
            raise ValueError(
                f"Got bad timezone for {app_name}: {iana_timezone}. "
                f"Use IANA timezones. {e}"
            ) from e

    def _decode_wire(self, raw: bytes) -> str:
        """Parent EOFFileWatcher returns UTF-8 encoded bytes."""
        return raw.decode()

    def _deserialize_wire(self, decoded: str) -> list[list[str]]:
        data_rows: list[list[str]] = []
        for row in csv.reader(io.StringIO(decoded)):
            if not row:
                continue

            # File re-read from start (failed ingest / rotate) re-presents headers.
            if self._header_loaded and (
                len(row) == 1 or row[0] == "ID" or row[0] in _HEADER_KEYS
            ):
                self._header_loaded = False
                self._headers.clear()

            if not self._header_loaded:
                if len(row) == 1:
                    self._headers["thing_uuid"] = row[0]
                elif row[0] == "ID":
                    self._headers["channel"] = row[1:]
                elif row[0] in _HEADER_KEYS:
                    continue
                if (
                    "thing_uuid" in self._headers
                    and "channel" in self._headers
                    and row[0] not in _HEADER_KEYS
                    and len(row) > 1
                ):
                    self._header_loaded = True
                    data_rows.append(row)
                continue
            # row: timestamp, value_1, ..., value_n (index → channel / Sensor)
            data_rows.append(row)
        return data_rows

    def _decapsulate_wire(
        self, wire_message: list[list[str]]
    ) -> DecapsulatedMessage:
        channels: list[str] = self._headers["channel"]
        wanted = [
            (i, ch, self._channel_sensor_map[ch])
            for i, ch in enumerate(channels)
            if ch in self._channel_sensor_map
        ]
        # One series per Sensor instance (not per quantity — quantities may repeat).
        series: dict[SensorUUID, list[Any]] = {uuid: [] for _, _, uuid in wanted}
        timestamps: list[datetime] = []
        for row in wire_message:
            timestamps.append(
                datetime.strptime(row[0], _TS).replace(tzinfo=self._timezone)
            )
            for i, _ch, uuid in wanted:
                series[uuid].append(row[i + 1])

        time_axis = IrregularTimeAxis(timestamps=timestamps)
        logger_id = self._headers["thing_uuid"]
        return DecapsulatedMessage(
            identified_payloads=[
                IdentifiedTimeSeriesPayload(
                    payload=values,
                    time_axis=time_axis,
                    thing_uuid=logger_id,
                    sensor_uuid=sensor_uuid,
                )
                for sensor_uuid, values in series.items()
            ],
        )
