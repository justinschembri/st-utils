"""Manage connections, authentication & protocols with sensor infrastructure"""

# standard
import os
import logging
import json
from abc import ABC, abstractmethod
from typing import Any, Literal
import time
import queue
import threading
import inspect

# external
import lnetatmo
from paho.mqtt.client import Client as mqttClient
from paho.mqtt.enums import CallbackAPIVersion

# internal
from .monitor import network_monitor
from .config import CREDENTIALS_DIR, TOKENS_DIR

# environment setup
CONTAINER_ENVIRONMENT = True if os.getenv("CONTAINER_ENVIRONMENT") else False
# type definitions
URL = str
# loggers got from main
main_logger = logging.getLogger("main")
event_logger = logging.getLogger("events")
debug_logger = logging.getLogger("debug")


class SensorApplicationConnection(ABC):
    """
    Abstract base class representing any connection to a sensor application.
    """

    def __init__(
        self,
        application_name: str,
        authentication_type: Literal["tokens", "credentials"],
        *,
        max_retries: int = 5,
    ):
        self.application_name = application_name
        self.authentication_type = authentication_type
        self.max_retries = max_retries
        # private:
        self._thread = None
        self._stop_event = threading.Event()
        self._authentication_file = (
            (TOKENS_DIR / f"{self.application_name}.json")
            if self.authentication_type == "tokens"
            else (CREDENTIALS_DIR / "application_credentials.json")
        )

    # dunder method over rides #################################################
    def __hash__(self) -> int:
        return hash(self.application_name)

    def __eq__(self, other) -> bool:
        if not isinstance(other, SensorApplicationConnection):
            return False
        if other.application_name == self.application_name:
            return True
        else:
            return False

    # class methods ############################################################
    @classmethod
    def from_config(cls, application_name: str, config: dict[str, Any]):
        """
        Create connection from config dict.

        Automatically discovers constructor parameters and maps config values.
        Subclasses rarely need to override this unless they have complex logic.
        """
        sig = inspect.signature(cls)

        kwargs: dict[str, Any] = {"application_name": application_name}

        for param_name in sig.parameters:
            if param_name in config:
                kwargs[param_name] = config[param_name]

        return cls(**kwargs)

    # abstract methods ########################################################
    @abstractmethod
    def _auth(self) -> Any:
        """
        Authenticate a connection through some means.
        """
        pass

    @abstractmethod
    def _pull_data(self) -> Any:
        """
        Retrieve 'raw' data from a sensor connection.

        Implemented for HTTP and MQTT seperately.
        """
        pass

    @abstractmethod
    def _pull_transform_push_loop(self) -> None:
        """
        Loop through data pulling, checking for dead connections.

        Implemnted for HTTP and MQTT seperately.
        """
        pass

    # threading methods  #######################################################
    def start_pull_transform_push_thread(self):
        """
        Spin up a thread and run the _loop method.
        """
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(
                target=self._pull_transform_push_loop,
                daemon=True,
                name=self.application_name,
            )
            self._thread.start()

    def stop_pull_transform_push_thread(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(5)


class HTTPSensorApplicationConnection(SensorApplicationConnection, ABC):
    """
    A long or short lived connection with a sensor application communicating
    over HTTP/S operating a PULL model.

    Parameters:
        host (URL): endpoint to request.
        max_connection_retries (int): Number of times to retry a request
            to the HTTP server before killing the connection.
        interval (int): the interval between requests.
    Methods:
        start: Start a thread and a request loop at `interval`.
        stop: Stop the thread.
    """

    def __init__(
        self,
        application_name: str,
        authentication_type: Literal["tokens", "credentials"],
        *,
        max_retries: int = 10,
        # TODO: interval should not be bound to the application. It is plausible
        # to have sensors with different observation intervals to fall under the
        # same application.
        request_interval: int = 300,
    ):
        super().__init__(
            application_name,
            authentication_type,
            max_retries=max_retries,
        )

        self.request_interval = request_interval
        self._last_payload: Any = None
        self._authenticated: bool = False

    def _pull_transform_push_loop(self) -> None:
        """
        Loop requests until failure.
        """
        restart_attempt = 0
        while not self._stop_event.is_set():
            try:
                self._pull_data()
                if not self._last_payload == self._pull_data():
                    ...
                    # unpacked_payload = application_unpacker(application_name, native_payload)
                    # for observation unpacked_payload:
                    # frost_transformer(sensor_model, observation)
                restart_attempt = 0
                time.sleep(self.request_interval)
            except KeyboardInterrupt:
                self.stop_pull_transform_push_thread()
                break
            except Exception as e:
                restart_attempt += 1
                main_logger.warning(
                    f"Thread {self.application_name} encountered an exception "
                    f"{e}. Sleeping and trying again."
                )
                time.sleep(300)
                if restart_attempt == self.max_retries:
                    self.stop_pull_transform_push_thread()
                    main_logger.critical(f"Thread {self.application_name} died: {e}.")


class MQTTSensorApplicationConnection(SensorApplicationConnection, ABC):
    """
    A long lived MQTT connection / subscription to an MQTT sensor application.

    Parameters:
        application_name(str): Name of the sensor application
        host(URL): MQTT broker host
        topic(str): MQTT topic to subscribe to
        port(int): MQTT broker port (default: 8883)
        token_file(Path | None): Path to tokens used for authentication, if any
        credentials_file(Path | None): Path to credentials used for authentication, if any
        max_retries(int): Number of consecutive timeout failures before stopping
        timeout(int): Timeout in seconds for waiting on new messages
    """

    def __init__(
        self,
        application_name: str,
        authentication_type: Literal["tokens", "credentials"],
        host: URL,
        topic: str,
        *,
        port: int = 8883,
        max_retries: int = 3,
        timeout: int = 300,
    ):
        super().__init__(
            application_name=application_name,
            authentication_type=authentication_type,
            max_retries=max_retries,
        )
        self.host = host
        self.port = port
        self.timeout = timeout
        self.topic = topic
        # private
        self._payload_queue = queue.Queue()
        self._subscribed: bool = False
        self._mqtt_client = mqttClient(CallbackAPIVersion.VERSION2)

    def _pull_data(self) -> None:
        """
        Establishes MQTT connection, subscribes to topic, and starts receiving messages.
        Messages are placed in the internal queue by the MQTT client's callback.
        """
        # auth is defined in the concrete implementations:
        self._auth()

        def on_message(client, userdata, message):
            self._payload_queue.put(json.loads(message.payload))

        self._mqtt_client.on_message = on_message
        # TODO: consider if this is the right place for handling failed connections.
        self._mqtt_client.connect(self.host, self.port)
        if self._mqtt_client.is_connected():
            event_logger.info(f"Connected to {self.host}/{self.application_name}")

        self._mqtt_client.subscribe(self.topic)
        self._subscribed = True
        self._mqtt_client.loop_start()

        return None

    def _pull_transform_push_loop(self) -> None:
        """
        Continuously processes messages from the queue until stopped.

        This runs in its own thread and:
        1. Pulls messages from the queue (populated by MQTT callback)
        2. Unpacks and transforms the payload
        3. Optionally pushes to FROST server

        Stops when _stop_event is set or after max_retries consecutive timeouts.
        """
        if not self._subscribed:
            self._pull_data()

        consecutive_timeouts = 0

        while not self._stop_event.is_set():
            try:
                application_payload = self._payload_queue.get(timeout=self.timeout)
                consecutive_timeouts = 0
                network_monitor.add_named_count(
                    "payloads_received", self.application_name, 1
                )
                debug_logger.debug(f"{application_payload=}")

                # sensor_model, native_payloads = application_unpacker(self.application_name, native_payload)
                # for n in native_payloads:
                #    frost_observation = (frost_transformer(sensor_model, n))
                #    frost_upload(frost_observation)

                sensor_model = ...
                main_logger.info(
                    f"Received payload from {self.application_name} "
                    f"from a {sensor_model} sensor."
                )

            except queue.Empty:
                # No data received within timeout period
                consecutive_timeouts += 1
                main_logger.warning(
                    f"No data received from {self.application_name} "
                    f"in {self.timeout} seconds. Consecutive timeouts: "
                    f"{consecutive_timeouts}/{self.max_retries}."
                )

                network_monitor.add_named_count(
                    "timeout_events", self.application_name, 1
                )

                if consecutive_timeouts >= self.max_retries:
                    main_logger.error(
                        f"Exceeded max retries ({self.max_retries}) for "
                        f"{self.application_name}. Stopping connection."
                    )
                    self._stop_event.set()
                    break

            except Exception as e:
                main_logger.error(
                    "Error processing payload from " f"{self.application_name}: {e}."
                )
                network_monitor.add_named_count(
                    "rejected_payloads", self.application_name, 1
                )

        main_logger.info(
            "Gracefully stopping MQTT connection for" f"{self.application_name}"
        )
        self._mqtt_client.loop_stop()
        self._mqtt_client.disconnect()
        self._subscribed = False


class NetatmoConnection(HTTPSensorApplicationConnection):
    """
    Netamo HTTP connection class. Endpoint for communicating with Netamo API.
    """

    _auth_obj: lnetatmo.ClientAuth

    def _auth(self) -> lnetatmo.ClientAuth:
        """Return a netatmo authentication token."""

        if self._authenticated:
            debug_logger.debug(f"{self.application_name} already authenticated.")
            return self._auth_obj

        if not self._authentication_file:
            raise FileNotFoundError("Must pass a token file for a Netatmo Conneciton.")

        self._auth_obj = lnetatmo.ClientAuth(credentialFile=self._authentication_file)
        self._authenticated = True
        return self._auth_obj

    def _pull_data(
        self,
    ) -> list[dict[str, Any]] | None:
        """Retrieve the latest untransformed observation set (one or more) from the Netatmo API."""
        self._auth()
        netatmo_connection = lnetatmo.WeatherStationData(self._auth_obj)
        return netatmo_connection.rawData


class TTSConnection(MQTTSensorApplicationConnection):
    """
    MQTT connection to 'TheThingsStack' MQTT servers.
    """

    def _auth(self) -> None:
        """Authenticate to TheThingsStack using application name and api key."""

        if not self._authentication_file:
            raise FileNotFoundError(
                f"Did not find credential file for {self.application_name}"
            )

        with open(self._authentication_file, "r") as f:
            credentials = json.load(f)
            api_key = credentials.get(self.application_name).get("api_key")
            if not api_key:
                raise KeyError(
                    f"Did not find `api_key` in {self._authentication_file}."
                )
        # TTS "usernames" are equivalent to the application names.
        self._mqtt_client.username_pw_set(self.application_name, api_key)
        self._mqtt_client.tls_set()
        return None
