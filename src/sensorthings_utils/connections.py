"""Manage connections, authentication & protocols with sensor infrastructure"""
import os
import logging
import json
from abc import ABC, abstractmethod
from typing import Any, Literal, ClassVar
import time
import queue
import threading
import traceback
import inspect
# external
import lnetatmo
from paho.mqtt.client import Client as mqttClient
from paho.mqtt.enums import CallbackAPIVersion

from sensorthings_utils.exceptions import FrostUploadFailure, UnregisteredSensorError
from sensorthings_utils.frost import frost_observation_upload
# internal
from .monitor import netmon
from .config import CREDENTIALS_DIR, TOKENS_DIR
from .transformers.application_unpackers import ApplicationUnpacker, NetatmoUnpacker, TTSUnpacker, UnpackError
from .transformers.types import SensorID, SupportedSensors
from .transformers.registry import TRANSFORMER_MAP
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
        app_name: str,
        authentication_type: Literal["tokens", "credentials"],
        *,
        max_retries: int = 1,
    ):
        self.app_name = app_name
        self.authentication_type = authentication_type
        self.max_retries = max_retries
        # private:
        self._thread = None
        self._stop_event = threading.Event()
        self._authentication_file = (
            (TOKENS_DIR / f"{self.app_name}.json")
            if self.authentication_type == "tokens"
            else (CREDENTIALS_DIR / "application_credentials.json")
        )
        self.sensor_registry: dict[SensorID, SupportedSensors]
    
    # class attributes #########################################################
    application_unpacker: ClassVar[ApplicationUnpacker]
    # dunder method over rides #################################################
    def __hash__(self) -> int:
        return hash(self.app_name)

    def __eq__(self, other) -> bool:
        if not isinstance(other, SensorApplicationConnection):
            return False
        if other.app_name == self.app_name:
            return True
        else:
            return False

    # class methods ############################################################
    @classmethod
    def from_config(
            cls, app_name: str, config: dict[str, Any]
            ) -> "SensorApplicationConnection":
        """
        Create connection from config dict.

        Automatically discovers constructor parameters and maps config values.
        Subclasses rarely need to override this unless they have complex logic.
        """
        sig = inspect.signature(cls)

        kwargs: dict[str, Any] = {"app_name": app_name}

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

        Implemented for HTTP and MQTT seperately.
        """
        pass
    # common methods ###########################################################
    def _process_payload(self, app_payload:dict[str, Any]) -> None:
        """Orcestrator function: processes a payload and pushes to FROST."""
        #TODO: successful unpack is a bit of a contrived obj.
        successful_unpack = self.application_unpacker.unpack(app_payload)
        for sensor_id, observations in successful_unpack.data.items():
            sensor_model = self.sensor_registry.get(sensor_id, None)
            if not sensor_model:
                raise UnregisteredSensorError
            transformer = TRANSFORMER_MAP[sensor_model]
            payload = transformer.from_unpack(
                    observations, 
                    successful_unpack.application_timestamp
                    )
            st_observations = payload.to_stObservations()
            for st_obs in st_observations:
                try:
                    frost_observation_upload(sensor_id, st_obs, self.app_name)
                    event_logger.info(
                        f"Received and processed a payload from {self.app_name} "
                        f"from a {sensor_model.value} sensor."
                    )
                    netmon.add_named_count(
                            "push_success", f"{sensor_id}", 1)
                except FrostUploadFailure as e:
                    self._exception_handler(e, sensor_id=sensor_id)

    def _exception_handler(self, e:Exception | None, **kwargs) -> Literal[0, 1]:
        """Exception handling, return 0 if transient error, 1 if system failure."""
        
        def _log(msg:str, debug_context:dict[str, str]):
            main_logger.error(msg)
            debug_logger.debug(debug_context)

        debug_context = {
                "application":f"{self.app_name}",
                "exception_type":f"{type(e)}",
                "exception_message":f"{e}",
                **kwargs
                }
        name = e.__repr__()
        if isinstance(e, UnpackError):
            msg = f"{name}: failed to unpack an application payload."
            _log((f"{self.app_name} " + msg), debug_context)
            return 0
        elif isinstance(e, queue.Empty):
            msg = f"{name}: MQTT queue is empty."
            _log((f"{self.app_name} " + msg), debug_context)
            return 0
        elif isinstance(e, UnregisteredSensorError):
            msg = f"{name}: sensor is not registered." 
            _log((f"{self.app_name} " + msg), debug_context)
            return 0
        elif isinstance(e, FrostUploadFailure):
            msg = f"{name}: failure to upload to FROST."
            _log((f"{self.app_name} " + msg), debug_context)
            return 1
        else:
            msg = f"{e}"
            msg += traceback.format_exc()
            _log((f"{self.app_name} " + msg), debug_context)
            return 1


    # threading methods  #######################################################
    def start_pull_transform_push_thread(
            self, sensor_registry:dict[SensorID, SupportedSensors]
            ):
        """
        Spin up a thread and run the _loop method.
        """
        self.sensor_registry = sensor_registry
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(
                target=self._pull_transform_push_loop,
                daemon=True,
                name=self.app_name,
            )
            self._thread.start()

    def stop_pull_transform_push_thread(self):
        self._stop_event.set()


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
        app_name: str,
        authentication_type: Literal["tokens", "credentials"],
        *,
        max_retries: int = 10,
        # TODO: interval should not be bound to the application. It is plausible
        # to have sensors with different observation intervals to fall under the
        # same application.
        request_interval: int = 300,
    ):
        super().__init__(
            app_name,
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
        failures = 0
        app_payload = None
        while not self._stop_event.is_set():
            try:
                app_payload = self._pull_data()
                if self._last_payload == app_payload:
                    # a bit of a 'magic number' here:
                    time.sleep(self.request_interval/4)
                    continue
                self._last_payload = app_payload
                self._process_payload(app_payload)
                netmon.add_named_count("payloads_received", self.app_name, 1)
                failures = 0
            except Exception as e:
                #TODO: consider carefully which exception types should be 'failures'
                failures += self._exception_handler(e, app_payload=app_payload)
                if failures == self.max_retries:
                    main_logger.critical(
                        f"Exceeded max retries ({self.max_retries}) for "
                        f"{self.app_name}. Stopping connection."
                    )
                    self._stop_event.set()

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
        app_name: str,
        authentication_type: Literal["tokens", "credentials"],
        host: URL,
        topic: str,
        *,
        port: int = 8883,
        max_retries: int = 3,
        timeout: int = 1200
    ):
        super().__init__(
            app_name,
            authentication_type,
            max_retries=max_retries,
        )
        self.host = host
        self.port = port
        self.topic = topic
        self.timeout = timeout
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
        self._mqtt_client.connect(self.host, self.port)
        if self._mqtt_client.is_connected():
            event_logger.info(f"Connected to {self.host}/{self.app_name}")
        self._mqtt_client.subscribe(self.topic)
        self._subscribed = True
        self._mqtt_client.loop_start()

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
            # will fill queue with app payloads:
            self._pull_data()

        failures = 0
        app_payload = None
        while not self._stop_event.is_set():
            try:
                app_payload = self._payload_queue.get(timeout=self.timeout)
                self._process_payload(app_payload)
                failures = 0
            except Exception as e:
                failures += self._exception_handler(e, app_payload=app_payload)
                if failures >= self.max_retries:
                    main_logger.critical(
                        f"Exceeded max retries ({self.max_retries}) for "
                        f"{self.app_name}. Stopping connection."
                    )
                    self._stop_event.set()

        event_logger.info(
            "Gracefully stopping MQTT connection for" f"{self.app_name}"
        )
        self._mqtt_client.loop_stop()
        self._mqtt_client.disconnect()
        self._subscribed = False



class NetatmoConnection(HTTPSensorApplicationConnection):
    """
    Netamo HTTP connection class. Endpoint for communicating with Netamo API.
    """
    _auth_obj: lnetatmo.ClientAuth
    application_unpacker = NetatmoUnpacker()

    def _auth(self) -> lnetatmo.ClientAuth:
        """Return a netatmo authentication token."""

        if self._authenticated:
            debug_logger.debug(f"{self.app_name} already authenticated.")
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
        if not self._authenticated:
            self._auth()
        netatmo_connection = lnetatmo.WeatherStationData(self._auth_obj)
        return netatmo_connection.rawData


class TTSConnection(MQTTSensorApplicationConnection):
    """
    MQTT connection to 'TheThingsStack' MQTT servers.
    """
    application_unpacker = TTSUnpacker() 

    def _auth(self) -> None:
        """Authenticate to TheThingsStack using application name and api key."""

        if not self._authentication_file:
            raise FileNotFoundError(
                f"Did not find credential file for {self.app_name}"
            )

        with open(self._authentication_file, "r") as f:
            credentials = json.load(f)
            api_key = credentials.get(self.app_name).get("api_key")
            if not api_key:
                raise KeyError(
                    f"Did not find `api_key` in {self._authentication_file}."
                )
        # TTS "usernames" are equivalent to the application names.
        self._mqtt_client.username_pw_set(self.app_name, api_key)
        self._mqtt_client.tls_set()
        return None

