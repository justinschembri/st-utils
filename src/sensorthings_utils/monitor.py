"""Background monitor for program performance."""

# standard
from datetime import datetime
import time
import logging
import threading
from collections import defaultdict
import sys

from sensorthings_utils.config import ROOT_DIR
from sensorthings_utils.transformers.types import SensorID

main_logger = logging.getLogger("network_monitor")
event_logger = logging.getLogger("events")
debug_logger = logging.getLogger("debug")

__all__ = ["netmon"]


class _NetworkMonitor:
    """
    Network monitor Singleton: stores sensor related telemetry.

    The network monitor should be used as a singleton shared across multiple
    modules.
    """

    def __init__(self):
        self.start_time = datetime.now()
        self.expected_sensors: set[SensorID] = set()
        self.starting_application_threads: set[str] = set()
        self.push_success: dict[SensorID, int] = defaultdict(int)
        self.push_fail: dict[SensorID, int] = defaultdict(int)
        self.last_push_time: dict[SensorID, float] = defaultdict(float)
        self.rejected_payloads: dict[SensorID, int] = defaultdict(int)
        self.sensor_config_fail: int = 0
        self.payloads_received: dict[str, int] = defaultdict(int)
        self.first_report_issued: bool = False
        self._lock = threading.Lock()

    def set_starting_threads(self, starting_threads: list[str] | set[str]):
        if not starting_threads:
            raise ValueError("No threads passed.")
        self.starting_application_threads = set(starting_threads)

    @property
    def live_threads(self):
        return set([i.name for i in threading.enumerate()])

    def add_count(self, attr: str, count: int = 1):
        with self._lock:
            v = self.__getattribute__(attr) + count
            self.__setattr__(attr, v)
        return None

    def reduce_count(self, attr: str, count: int = 1):
        with self._lock:
            v = self.__getattribute__(attr) - count
            self.__setattr__(attr, v)
        return None

    def add_named_time(self, attr: str, application: str, time: float):
        with self._lock:
            self.__getattribute__(attr)[application] = time

    def add_named_count(self, attr: str, application: str, count: int = 1):
        """For counts associated with named applications."""

        with self._lock:
            self.__getattribute__(attr)[application] += count

    def _to_html(self, health_report: list[str]) -> None:
        health_file_html = ROOT_DIR / "logs" / "health.html"

        html_lines = [
            "<!DOCTYPE html>",
            "<html lang='en'>",
            "<head>",
            "  <meta charset='UTF-8'>",
            "  <title>STA-utils Health Report</title>",
            "  <style>",
            "    body { font-family: monospace; background: #f4f4f4; padding: 20px; }",
            "    .info { color: black; }",
            "    .warning { color: darkorange; font-weight: bold; }",
            "    .down {color: red; font-weight:bold; }",
            "    .header { font-weight: bold; font-size: 1.2em; margin-top: 1em; }",
            "  </style>",
            "</head>",
            "<body>",
            "  <h1>ST-Utils Health Report</h1>",
            "  <p> st-utils instance <p>",
            f" <p> Time of report: {str(datetime.now()).split('.')[0]} </p>",
            "  <h2> Periodic Health Report </h2>",
        ]

        for line in health_report:
            if "warning" in line.lower():
                cls = "warning"
            elif "down" in line.lower():
                cls = "down"
            else:
                cls = "info"
            html_lines.append(f"  <p class='{cls}'>{line}</p>")

        html_lines.append("</body></html>")
        with open(health_file_html, "w", encoding="utf-8") as f:
            f.write("\n".join(html_lines))

    def report(self, interval: int = 60):
        if not self.first_report_issued:
            time.sleep(360)
            self.first_report_issued = True
        else:
            time.sleep(60 * interval)

        health_report: list[str] = [
            "st-utils instance",
        ]
        with self._lock:
            # Report on active threads.
            dead_threads = self.starting_application_threads - self.live_threads
            thread_msg = (
                f"All original threads alive: {self.starting_application_threads}."
                if not dead_threads
                else f"Some threads have died: {dead_threads}. Killing app."
            )
            if not dead_threads:
                event_logger.info(thread_msg)
            else:
                main_logger.warning(thread_msg)
                # TODO: instead of killing the app - restart the dead threads -
                # furthermore this should NOT be the responsibility of the
                # network monitor.
                sys.exit(1)
            health_report.append(thread_msg)
            # Report succesful pushes:
            uptime = str((datetime.now() - self.start_time))
            uptime = uptime.split(".")[0] + " hrs"
            msg = f"Uptime: {uptime}"
            health_report.append(msg)
            main_logger.info(msg)
            for k, v in self.payloads_received.items():
                msg = f"Payloads received from {k} : {v}"
                health_report.append(msg)
                main_logger.info(msg)
            for k, v in self.rejected_payloads.items():
                msg = f"Payloads rejected for {k} : {v}"
                health_report.append(msg)
                main_logger.warning(msg)
            for i, (k, v) in enumerate(self.push_success.items()):
                time_since_last_push = (time.time() - self.last_push_time[k]) / 60
                warning_msg = "WARNING: " if time_since_last_push > 60 else ""
                msg = (
                    f"{i+1} →  {k} → {v} observations pushed. "
                    f"{warning_msg}→ Time since last push: "
                    f"{time_since_last_push:.2f}m."
                )
                health_report.append(msg)
                main_logger.info(msg)
            for k, v in self.push_fail.items():
                msg = f"Rejected observations for {k} →  {v}"
                health_report.append(msg)
                main_logger.warning(msg)

            non_responsive_applications = self.expected_sensors - (
                self.push_success.keys()
            )
            for _ in non_responsive_applications:
                msg = f"Data never received from {_}, sensor may be down."
                health_report.append(msg)
                main_logger.warning(msg)
            main_logger.info("Check logs for full details.")

        self._to_html(health_report)


# TODO: wrap in a function and implement lazy importing
netmon = _NetworkMonitor()
