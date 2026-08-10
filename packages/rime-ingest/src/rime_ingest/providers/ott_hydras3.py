"""Support for OTT Hydras 3 hydrometric station plaintext exports.

OTT Hydras 3 (and related station software) writes dated directories of
`.MIS`-style text files. Each file is a sectioned snapshot, not an append
log::

    <STATION>…</STATION><SENSOR>…</SENSOR><DATEFORMAT>YYYYMMDD</DATEFORMAT>
    YYYYMMDD;HHMMSS;value
    …

Sections rewrite as new samples arrive. This provider polls via
:class:`DiffDirectoryWatcher`: the wire message is a line-set diff of new
lines, while framing (station / sensor headers) is read from
`source_snapshot.content`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from rime_ingest.transformers.messages import (
    DecapsulatedMessage,
    IdentifiedTimeSeriesPayload,
    IrregularTimeAxis,
)
from rime_ingest.transformers.types import SensorUUID

from ..transport.poll.fs import DiffDirectoryWatcher

_TS = "%Y%m%d%H%M%S"
_HEADER_RE = re.compile(
    r"<STATION>(?P<station>[^<]+)</STATION>"
    r"<SENSOR>(?P<sensor>[^<]+)</SENSOR>"
    r"<DATEFORMAT>(?P<dateformat>[^<]+)</DATEFORMAT>"
)


@dataclass(frozen=True)
class _SensorBatch:
    """New samples for one station/sensor section."""

    station: str
    sensor_id: str
    timestamps: list[datetime]
    values: list[str]


def _parse_sections(text: str) -> list[tuple[str, str, list[str]]]:
    """Split a full `.MIS` body into `(station, sensor_id, data_lines)`."""
    sections: list[tuple[str, str, list[str]]] = []
    station: str | None = None
    sensor_id: str | None = None
    rows: list[str] = []

    def _flush() -> None:
        nonlocal station, sensor_id, rows
        if station is not None and sensor_id is not None:
            sections.append((station, sensor_id, rows))
        rows = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = _HEADER_RE.fullmatch(line)
        if match:
            _flush()
            station = match.group("station")
            sensor_id = match.group("sensor")
            continue
        if station is None or sensor_id is None:
            continue
        rows.append(line)
    _flush()
    return sections


class OTTHydra3Provider(DiffDirectoryWatcher):
    """Poll OTT Hydras 3 `.MIS` snapshots → one time-series per mapped Sensor.

    `channel_sensor_map` maps vendor sensor ids from `<SENSOR>…</SENSOR>`
    (e.g. `0010`) to STA Sensor UUIDs. Quantity routing stays on the model
    tier; this provider only strips section framing and attaches identity.
    """

    def __init__(
        self,
        app_name: str,
        *,
        root_dir: str | Path,
        file_glob: str,
        iana_timezone: str,
        channel_sensor_map: dict[str, str],
        max_retries: int = 10,
        poll_interval: float = 300,
        encoding: str = "utf-8",
        backfill: bool = True,
    ):
        super().__init__(
            app_name,
            root_dir=root_dir,
            file_glob=file_glob,
            max_retries=max_retries,
            poll_interval=poll_interval,
            encoding=encoding,
            backfill=backfill,
        )
        self._channel_sensor_map: dict[str, SensorUUID] = dict(channel_sensor_map)
        try:
            self._timezone = ZoneInfo(iana_timezone)
        except Exception as e:
            raise ValueError(
                f"Got bad timezone for {app_name}: {iana_timezone}. "
                f"Use IANA timezones. {e}"
            ) from e

    def _decode_wire(self, raw: bytes) -> str:
        """DiffDirectoryWatcher forwards UTF-8 (or configured) line-diff bytes."""
        return raw.decode(self.encoding)

    def _deserialize_wire(self, decoded: str) -> list[_SensorBatch]:
        """Attribute new diff lines to sections using the full source snapshot."""
        if self.source_snapshot is None:
            raise RuntimeError(
                f"{self.app_name}: source_snapshot missing during deserialize"
            )

        full = self.source_snapshot.content.decode(self.encoding)
        new_lines = {line.strip() for line in decoded.splitlines() if line.strip()}
        batches: list[_SensorBatch] = []

        for station, sensor_id, row_lines in _parse_sections(full):
            if sensor_id not in self._channel_sensor_map:
                continue
            timestamps: list[datetime] = []
            values: list[str] = []
            for line in row_lines:
                if line not in new_lines:
                    continue
                date_s, time_s, value = line.split(";", maxsplit=2)
                timestamps.append(
                    datetime.strptime(f"{date_s}{time_s}", _TS).replace(
                        tzinfo=self._timezone
                    )
                )
                values.append(value)
            if timestamps:
                batches.append(
                    _SensorBatch(
                        station=station,
                        sensor_id=sensor_id,
                        timestamps=timestamps,
                        values=values,
                    )
                )
        return batches

    def _decapsulate_wire(
        self, wire_message: list[_SensorBatch]
    ) -> DecapsulatedMessage:
        payloads: list[IdentifiedTimeSeriesPayload] = []
        for batch in wire_message:
            payloads.append(
                IdentifiedTimeSeriesPayload(
                    payload=batch.values,
                    time_axis=IrregularTimeAxis(timestamps=batch.timestamps),
                    thing_uuid=batch.station,
                    sensor_uuid=self._channel_sensor_map[batch.sensor_id],
                )
            )
        return DecapsulatedMessage(identified_payloads=payloads)
