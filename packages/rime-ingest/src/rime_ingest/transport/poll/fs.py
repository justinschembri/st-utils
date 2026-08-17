"""Poll the filesystem for new file content.

EOF watchers treat files as append-oriented: only bytes past the last read
offset are forwarded. Truncation or an inode change under the same path
(log rotate / atomic replace) resets the offset.

`DiffDirectoryWatcher` tracks ``current_file`` / ``last_file``. On rollover it
does a one-shot drain of the outgoing file, then follows only the new path.
Providers can read framing from ``source_snapshot.content`` while ingesting the
wire diff.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from ...monitor import netmon
from ..base import SensorTransport

main_logger = logging.getLogger("main")
event_logger = logging.getLogger("events")


@dataclass
class FileCursor:
    offset: int = 0
    last_ino: int | None = None


@dataclass
class SnapshotState:
    """Full-file snapshot used as a diff baseline for one path."""

    content: bytes = b""
    mtime_ns: int | None = None
    size: int | None = None
    ino: int | None = None

    def read_diff(self, path: Path, *, app_name: str) -> bytes | None:
        """Re-read ``path`` when metadata changes; return line-set diff vs last content."""
        st = path.stat()
        if (
            self.mtime_ns == st.st_mtime_ns
            and self.size == st.st_size
            and self.ino == st.st_ino
        ):
            return None

        content = path.read_bytes()
        diff = line_set_diff(self.content, content)
        self.content = content
        self.mtime_ns = st.st_mtime_ns
        self.size = st.st_size
        self.ino = st.st_ino
        if diff is None and self.content:
            event_logger.debug(
                f"{app_name}: {path} metadata changed but line content identical"
            )
        return diff


def discover_latest_file(root_dir: Path, file_glob: str) -> Path | None:
    """Return the newest regular file under `root_dir` matching `file_glob`."""
    candidates = discover_files(root_dir, file_glob)
    if not candidates:
        return None
    return candidates[-1]


def discover_files(root_dir: Path, file_glob: str) -> list[Path]:
    """Return matching files under ``root_dir``, oldest → newest."""
    candidates = [p for p in root_dir.glob(file_glob) if p.is_file()]
    candidates.sort(key=lambda p: (p.stat().st_mtime, p.as_posix()))
    return candidates


def read_appended_bytes(path: Path, cursor: FileCursor, *, app_name: str) -> bytes | None:
    """Read newly appended bytes from `path`, updating `cursor` in place.

    Returns the unread chunk, or `None` when there is nothing new to read.
    """
    st = path.stat()
    offset = cursor.offset

    if cursor.last_ino is not None and st.st_ino != cursor.last_ino:
        event_logger.info(
            f"{app_name}: inode changed for {path}; resetting read offset."
        )
        offset = 0
    cursor.last_ino = st.st_ino

    if st.st_size < offset:
        event_logger.info(f"{app_name}: {path} truncated; resetting read offset")
        offset = 0

    if st.st_size == offset:
        cursor.offset = offset
        return None

    with path.open("rb") as f:
        f.seek(offset)
        chunk = f.read()

    if not chunk:
        cursor.offset = offset
        return None

    cursor.offset = offset + len(chunk)
    return chunk


def line_set_diff(previous: bytes, current: bytes) -> bytes | None:
    """Return newline-joined lines present in `current` but not `previous`.

    Order is not preserved (set difference). Empty result → `None`.
    """
    prev = set(previous.splitlines())
    added = [line for line in current.splitlines() if line not in prev]
    if not added:
        return None
    return b"\n".join(added)


class EOFFileWatcher(SensorTransport):
    """Poll one append-only file for newly appended bytes.

    Parameters:
        app_name: Application identifier.
        max_retries: Consecutive failures tolerated before the thread stops.
        file_path: Concrete path to the watched file.
        poll_interval: Seconds between polls when idle or after a successful read.
        encoding: Text encoding for wire decoding (provider use).
    """

    def __init__(
        self,
        app_name: str,
        *,
        max_retries: int = 10,
        file_path: str | Path,
        poll_interval: float = 300,
        encoding: str = "utf-8",
    ):
        super().__init__(app_name, max_retries=max_retries)
        self.file_path = Path(file_path)
        self.poll_interval = poll_interval
        self.encoding = encoding
        self._cursor = FileCursor()

    def _run(self) -> None:
        failures = 0
        wire_message = None
        while not self._stop_event.is_set():
            try:
                wire_message = read_appended_bytes(
                    self.file_path, self._cursor, app_name=self.app_name
                )
                if wire_message is None:
                    self._stop_event.wait(self.poll_interval)
                    continue

                self._process_wire_message(wire_message)
                netmon.add_named_count("messages_received", self.app_name, 1)
                failures = 0
                self._stop_event.wait(self.poll_interval)
            except Exception as e:
                failures += self._exception_handler(e, wire_message=wire_message)
                if failures >= self.max_retries:
                    main_logger.critical(
                        f"Exceeded max retries ({self.max_retries}) for "
                        f"{self.app_name}. Killing thread."
                    )
                    self._stop_event.set()


class EOFDirectoryWatcher(SensorTransport):
    """Discover and EOF-tail the latest append-only file under a directory tree.

    Each poll globs `root_dir` with `file_glob`, picks the newest `st_mtime`
    match, and reads appended bytes. On rollover the previous path lingers until
    fully read.
    """

    def __init__(
        self,
        app_name: str,
        *,
        root_dir: str | Path,
        file_glob: str,
        max_retries: int = 10,
        poll_interval: float = 300,
        encoding: str = "utf-8",
    ):
        super().__init__(app_name, max_retries=max_retries)
        self.root_dir = Path(root_dir)
        self.file_glob = file_glob
        self.poll_interval = poll_interval
        self.encoding = encoding
        self._cursors: dict[Path, FileCursor] = {}

    def _prune_linger(self, active: Path | None) -> None:
        for path in list(self._cursors):
            if path == active:
                continue
            cursor = self._cursors[path]
            if not path.is_file() or cursor.offset >= path.stat().st_size:
                event_logger.info(f"{self.app_name}: finished linger on {path}")
                del self._cursors[path]

    def _run(self) -> None:
        failures = 0
        wire_message = None
        while not self._stop_event.is_set():
            try:
                active = discover_latest_file(self.root_dir, self.file_glob)
                if active is not None and active not in self._cursors:
                    event_logger.info(f"{self.app_name}: watching {active}")
                    self._cursors[active] = FileCursor()

                for path in list(self._cursors):
                    wire_message = read_appended_bytes(
                        path, self._cursors[path], app_name=self.app_name
                    )
                    if wire_message is None:
                        continue
                    self._process_wire_message(wire_message)
                    netmon.add_named_count("messages_received", self.app_name, 1)

                self._prune_linger(active)
                failures = 0
                self._stop_event.wait(self.poll_interval)
            except Exception as e:
                failures += self._exception_handler(e, wire_message=wire_message)
                if failures >= self.max_retries:
                    main_logger.critical(
                        f"Exceeded max retries ({self.max_retries}) for "
                        f"{self.app_name}. Killing thread."
                    )
                    self._stop_event.set()


class DiffDirectoryWatcher(SensorTransport):
    """Discover snapshot / rewrite files and emit line-set diffs on change.

    ``current_file`` / ``current_snapshot`` are the active path. On rollover the
    outgoing file is drained once, then kept as ``last_file`` / ``last_snapshot``
    for provider access (headers / full text) until the next rollover. Only
    ``current_file`` is polled thereafter.

    Before each ``_process_wire_message``, ``source_file`` / ``source_snapshot``
    point at the path whose diff is being processed.

    Parameters:
        app_name: Application identifier.
        root_dir: Root directory searched via :meth:`pathlib.Path.glob`.
        file_glob: Glob pattern relative to ``root_dir`` (e.g. ``"????????/*.MIS"``).
        poll_interval: Seconds between polls.
        encoding: Text encoding for wire decoding (provider use).
        max_retries: Consecutive failures tolerated before the thread stops.
    """

    def __init__(
        self,
        app_name: str,
        *,
        root_dir: str | Path,
        file_glob: str,
        max_retries: int = 10,
        poll_interval: float = 300,
        encoding: str = "utf-8",
        backfill: bool = True,
    ):
        super().__init__(app_name, max_retries=max_retries)
        self.root_dir = Path(root_dir)
        self.file_glob = file_glob
        self.poll_interval = poll_interval
        self.encoding = encoding
        self.backfill = backfill
        self.current_file: Path | None = None
        self.last_file: Path | None = None
        self.current_snapshot: SnapshotState | None = None
        self.last_snapshot: SnapshotState | None = None
        self.source_file: Path | None = None
        self.source_snapshot: SnapshotState | None = None

    def _emit_diff(self, path: Path, snapshot: SnapshotState) -> None:
        wire_message = snapshot.read_diff(path, app_name=self.app_name)
        if wire_message is None:
            return
        self.source_file = path
        self.source_snapshot = snapshot
        self._process_wire_message(wire_message)
        netmon.add_named_count("messages_received", self.app_name, 1)

    def _adopt_current(self, path: Path) -> None:
        if self.current_file is None:
            event_logger.info(f"{self.app_name}: watching {path}")
            self.current_file = path
            self.current_snapshot = SnapshotState()
            return

        if path == self.current_file:
            return

        event_logger.info(f"{self.app_name}: rollover {self.current_file} → {path}")
        self._emit_diff(self.current_file, self.current_snapshot)
        self.last_file = self.current_file
        self.last_snapshot = self.current_snapshot
        self.current_file = path
        self.current_snapshot = SnapshotState()

    def _backfill(self) -> None:
        """Emit every matching file once (oldest → newest), then watch the latest."""
        files = discover_files(self.root_dir, self.file_glob)
        if not files:
            event_logger.info(f"{self.app_name}: backfill found no files")
            return
        event_logger.info(f"{self.app_name}: backfilling {len(files)} files")
        for path in files:
            if self._stop_event.is_set():
                return
            try:
                snapshot = SnapshotState()
                self.current_file = path
                self.current_snapshot = snapshot
                self._emit_diff(path, snapshot)
                self.last_file = path
                self.last_snapshot = snapshot
            except Exception as e:
                event_logger.warning(
                    f"{self.app_name}: backfill skipped {path}: {e!r}"
                )
                continue
        event_logger.info(
            f"{self.app_name}: backfill complete; watching {self.current_file}"
        )

    def _run(self) -> None:
        failures = 0
        wire_message = None
        try:
            if self.backfill:
                self._backfill()
        except Exception as e:
            failures += self._exception_handler(e, wire_message=wire_message)
            event_logger.warning(
                f"{self.app_name}: backfill interrupted ({e!r}); "
                "continuing with live poll"
            )

        while not self._stop_event.is_set():
            try:
                discovered = discover_latest_file(self.root_dir, self.file_glob)
                if discovered is not None and discovered != self.current_file:
                    self._adopt_current(discovered)

                if (
                    self.current_file is not None
                    and self.current_snapshot is not None
                ):
                    self._emit_diff(self.current_file, self.current_snapshot)

                failures = 0
                self._stop_event.wait(self.poll_interval)
            except Exception as e:
                failures += self._exception_handler(e, wire_message=wire_message)
                if failures >= self.max_retries:
                    main_logger.critical(
                        f"Exceeded max retries ({self.max_retries}) for "
                        f"{self.app_name}. Killing thread."
                    )
                    self._stop_event.set()
