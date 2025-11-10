"""Background monitor for program performance."""

# standard
from datetime import datetime
import time
import logging
import threading
from collections import defaultdict
import sys

from sensorthings_utils.config import ROOT_DIR

logger = logging.getLogger("network_monitor")

__all__ = ["network_monitor"]

class _NetworkMonitor:
    """
    Network monitor Singleton: stores sensor related telemetry.

    The network monitor should be used as a singleton shared across multiple 
    modules.
    """

    def __init__(self):
        self.start_time = datetime.now()
        self.starting_application_threads: set[str] = set()
        self.push_success: dict[str, int] = defaultdict(int)
        self.push_fail: dict[str, int] = defaultdict(int)
        self.last_push_time: dict[str, float] = defaultdict(float)
        self.rejected_payloads: dict[str, int] = defaultdict(int)
        self.sensor_config_fail: int = 0
        self.payloads_received: dict[str, int] = defaultdict(int)
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

    def report(self, interval: int = 30):
        time.sleep(60 * interval)
        health_report: list[str] = [
                "st-utils instance", 
                "Time of report:",
                str(datetime.now())
                ]

        with self._lock:
            # Report on active threads.
            dead_threads = self.starting_application_threads - self.live_threads
            thread_msg = (
                f"All original threads alive: {self.starting_application_threads}."
                if not dead_threads
                else f"Some threads have died: {dead_threads}. Killing app."
            )
            header_msg = (
                    f"Periodic Health Report" +
                    f"{"-"*(len(thread_msg)-len("Period Health Report"))}"
            ) 
            health_report.append(header_msg)
            logger.info(header_msg)
            if not dead_threads:
                logger.info(thread_msg)
            else:
                logger.warning(thread_msg)
                sys.exit(1)
            health_report.append(thread_msg)
            # Report succesful pushes:
            msg = f"Uptime: {datetime.now() - self.start_time}" 
            health_report.append(msg)
            logger.info(msg)
            if self.sensor_config_fail > 0:
                msg = (
                        f"{self.sensor_config_fail} sensor configuration " + 
                        f"file/s are invalid!"
                       )
                health_report.append(msg)
                logger.warning(msg)
            for k, v in self.payloads_received.items():
                msg = f"Payloads received from {k} : {v}"
                health_report.append(msg)
                logger.info(msg)
            for k, v in self.rejected_payloads.items():
                msg = f"Payloads rejected for {k} : {v}"
                health_report.append(msg)
                logger.warning(msg)
            for i, (k, v) in enumerate(self.push_success.items()):
                time_since_last_push = (time.time() - self.last_push_time[k]) / 60
                warning_msg = "WARNING: " if time_since_last_push > 60 else ""
                msg = (
                        f"{i} - Observations created for {k} : {v} " + 
                        f"{warning_msg}Time since last push: " +
                        f"{time_since_last_push:.2f}m)." 
                    )
                health_report.append(msg)
                logger.info(msg)
            for k, v in self.push_fail.items():
                msg = f"Rejected observations for {k} : {v}"
                health_report.append(msg)
                logger.warning(msg)
            for k, v in self.last_push_time.items():
                if v - time.time() > 3600:
                    msg = f"Have not received observations from {k} in {v:.2f}."
                    health_report.append(msg)
                    logger.warning(msg)

            logger.info("Check logs for full details.")
        
        health_file = ROOT_DIR / "logs" / "health.log"
        with open(health_file, "w", encoding="utf-8") as f:
            f.write("\n".join(health_report) + "\n")

network_monitor = _NetworkMonitor()

