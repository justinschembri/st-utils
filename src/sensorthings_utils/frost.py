"""Interactions with FROST API."""

# standard
import urllib.request as request
from urllib.parse import quote
from urllib import error
from typing import Dict, Tuple, Any, Union, TYPE_CHECKING
import time
import json
import logging
import os
import re

# internal
from sensorthings_utils.config import (
    CONTAINER_ENVIRONMENT,
    FROST_ENDPOINT_DEFAULT,
    FROST_CREDENTIALS,
)
from sensorthings_utils.exceptions import FrostUploadFailure
from sensorthings_utils.sensor_things.core import (
    Datastream,
    SensorThingsObject,
    Observation,
)
from sensorthings_utils.monitor import netmon
from sensorthings_utils.transformers.types import ObservedProperties, SensorID

# typing
if TYPE_CHECKING:
    from sensorthings_utils.sensor_things.extensions import SensorArrangement

UrlStr = str

logger = logging.getLogger(__name__)
debug_logger = logging.getLogger("debug")

ENTITY_ENDPOINTS: Dict[str, str] = {
    "Sensor": "/Sensors",
    "Datastream": "/Datastreams",
    "ObservedProperty": "/ObservedProperties",
    "Thing": "/Things",
    "Observation": "/Observations",
    "FeatureOfInterest": "/FeaturesOfInterest",
    "HistoricalLocation": "/HistoricalLocations",
    "Location": "/Locations",
}


def _check_frost_connection() -> None:
    """Check that FROST is functionally active."""

    frost_endpoint = os.getenv("FROST_ENDPOINT") or FROST_ENDPOINT_DEFAULT
    datastream_url = frost_endpoint + "/Datastreams"
    general_error_msg = (
        f"FROST server at {frost_endpoint} not active. "
        + "If you believe the server is up, check the environment "
        + "variable $FROST_ENDPOINT."
    )
    try:
        with request.urlopen(datastream_url) as _:
            logger.info("FROST connectivity confirmed.")
            return None
    except error.HTTPError as e:
        raise ConnectionError(f"{e}. {general_error_msg}") from None
    except error.URLError as e:
        raise ConnectionError(f"{e}. {general_error_msg}") from None


def check_existing_object(
    entity: "SensorThingsObject", container_environment: bool
) -> bool:
    """
    Check if an existing SensorThingsObject already exists.
    """
    match entity.st_type:
        case (
            "Sensor"
            | "Thing"
            | "ObservedProperty"
            | "Locations"
        ):  # TODO: #5 Sort out references, sometimes plural, sometimes singular.
            if filter_query(
                entity=ENTITY_ENDPOINTS[entity.st_type],
                filter_string=f"name eq '{entity.name}'",
                url=None,
                container_environment=CONTAINER_ENVIRONMENT,
            )["value"]:
                return True
        case "Datastream":
            # first, check if a datastream with a common name exists:
            initial_response = filter_query(
                entity="/Datastreams",
                filter_string=f"name eq '{entity.name}'",
                url=None,
                container_environment=CONTAINER_ENVIRONMENT,
            )["value"]
            # second, check if any of the datastreams with the same name also share a
            # link with the sensor of the entity being checked by this function
            if initial_response:
                # If multiple sensors of the same type exist, `response` will be an
                # array of datastreams. Iterate through all of responses:
                for i in range(len(initial_response)):
                    sensor_url = initial_response[i]["Sensor@iot.navigationLink"]  # type: ignore
                    if container_environment:
                        sensor_url = sensor_url.replace("localhost", "web")
                    # TODO: #10 Handling of
                    # localhost and web in containerized environments.
                    sensor_request = request.Request(url=sensor_url, method="GET")
                    with request.urlopen(sensor_request) as response:
                        response = json.loads(response.read())
                        response = response["name"]
                        if response == entity.iot_links["sensors"][0].name:  # type: ignore
                            return True
    return False


# TODO: Consider type overloads for return.
def filter_query(
    filter_string: str,
    entity: str | None,
    url: str | None,
    container_environment: bool,
) -> Dict[str, Any]:
    """
    Query the FROST server and return result.

    Open ended `filter_string`. If no `url` is passed, execpt an entity type to
    query.

    :param filter_string: URL encoded query string.
    :type filter_string: str
    :param entity: FROST entity (sensor, observations, etc.)
    :type entity: str
    :param container_environment: True is running in a container env.
    :type container_environment: bool

    """
    frost_endpoint = os.getenv("FROST_ENDPOINT") or FROST_ENDPOINT_DEFAULT
    if not url:
        query_url = frost_endpoint + f"{entity}?$filter=" + quote(filter_string)
    else:
        query_url = url + "?$filter=" + quote(filter_string)
    if container_environment:
        query_url = query_url.replace("localhost", "web")
    get_request = request.Request(url=query_url, method="GET")
    try:
        with request.urlopen(get_request) as response:
            response = json.loads(response.read())
            return response
    except error.URLError as e:
        logger.critical(
            "FROST connection refused, pointing to "
            f"{frost_endpoint}. Is server up and listening? "
            f"{get_request.full_url=}"
        )
        raise error.URLError(e)


def initial_setup(sensor_arrangement: "SensorArrangement") -> str:
    """
    Initial set up of a Sensor Arrangement on the FROST server. Returns the
    name of the sensor model.

    Commit the sensor arrangement to the FROST server, including the
    relationships between the sensor things objects. This process occurs only
    when setting up an arranagement for the first time.
    """

    _check_frost_connection()
    debug_logger.debug(sensor_arrangement.get_entities("Thing"))
    for thing in sensor_arrangement.get_entities("Thing"):
        make_thing = make_frost_object(thing)
        debug_logger.debug(make_thing)
        if not make_thing:
            break
        iot_url = make_thing["locations_url"]
        # lookup linked locations of the thing and make them:
        for loc in thing.iot_links["locations"]:
            # pass URL of newly generated Thing's Locations to the maker:
            debug_logger.debug(make_frost_object(loc, iot_url))
    # Make Sensors, which are associated only with Datastreams, which are linked later
    for sen in sensor_arrangement.get_entities("Sensor"):
        debug_logger.debug(make_frost_object(sen))
        sensor_model = sen.name
    # Make ObservedProperties, also linked later with a Datastream
    for op in sensor_arrangement.get_entities("ObservedProperty"):
        debug_logger.debug(make_frost_object(op))
    # Make Datastreams, linked with a one Sensor, one ObservedProperty and one Thing
    for ds in sensor_arrangement.get_entities("Datastream"):
        # Lookup the names's of the relevant Sensor, ObservedProperty and Thing:
        sen_name = ds.iot_links["sensors"][0].name  # only 1 object in list
        oprop_name = ds.iot_links["observedProperties"][0].name
        thing_name = ds.iot_links["things"][0].name
        # Query server and lookup ids:
        debug_logger.info(locals())
        sen_id = filter_query(
            entity="/Sensors",
            filter_string=f"name eq '{sen_name}'",
            url=None,
            container_environment=CONTAINER_ENVIRONMENT,
        )["value"][0]["@iot.id"]  # type: ignore
        oprop_id = filter_query(
            entity="/ObservedProperties",
            filter_string=f"name eq '{oprop_name}'",
            url=None,
            container_environment=CONTAINER_ENVIRONMENT,
        )["value"][0]["@iot.id"]  # type: ignore
        thing_id = filter_query(
            entity="/Things",
            filter_string=f"name eq '{thing_name}'",
            url=None,
            container_environment=CONTAINER_ENVIRONMENT,
        )["value"][0]["@iot.id"]  # type: ignore
        make_frost_datastream(
            ds,
            sensor_id=int(sen_id),
            thing_id=int(thing_id),
            observed_property_id=int(oprop_id),
        )
    return sensor_model


def make_frost_object(
    entity: Union["SensorThingsObject", "Observation"],
    iot_url: str | None = None,
    application_name: str | None = None,
) -> Dict[str, str]:
    """
    Add a a SensorThingsObject to the FROST server, return FROST IoT Link.

    Pass a SensorThingsObject and add it to FROST. Passing an `iot_url` pushes
    the object FROST URL (i.e., links the passed object to the the object) in
    the IoT URL.
    """

    frost_endpoint = os.getenv("FROST_ENDPOINT") or FROST_ENDPOINT_DEFAULT
    if check_existing_object(entity, CONTAINER_ENVIRONMENT):
        logger.info(f"Creation Skipped: {entity.st_type} {entity.name} already exists.")
        return {}

    expected_links_map: Dict[str, Tuple[str, ...]] = {
        "Sensor": ("Datastreams",),
        "Datastream": ("ObservedProperties", "Observations", "Sensors", "Things"),
        "ObservedProperty": ("Datastreams",),
        "Thing": ("Datastreams", "HistoricalLocations", "Locations"),
        "Observation": ("Datastream", "FeatureOfInterest"),
        "FeatureOfInterest": ("Observations",),
        "HistoricalLocation": ("Things", "Locations"),
        "Location": ("HistoricalLocations", "Things"),
    }

    application_name = application_name or ""
    expected_links = expected_links_map[entity.st_type]
    url = iot_url or (frost_endpoint + ENTITY_ENDPOINTS[entity.st_type])
    if CONTAINER_ENVIRONMENT:
        url = url.replace("localhost", "web")

    post_request = request.Request(
        url=url,
        data=entity.model_dump_json(exclude={"iot_links", "id", "st_type"}).encode(
            "UTF-8"
        ),
        method="POST",
    )
    post_request.add_header("Content-Type", "application/json")
    post_request.add_header("Authorization", f"Basic {FROST_CREDENTIALS}")

    try:
        with request.urlopen(post_request) as response:
            new_object_url = response.getheader(
                "Location"
            )  # "Location" does not refer to a SensorThings Location
            logger.info(f"New {entity.st_type} created at {new_object_url}")
            if entity.st_type == "Observation":
                sensor_name = observation_to_sensor_trace(new_object_url)
                if sensor_name:
                    netmon.add_named_count(
                        "push_success", sensor_name, 1
                    )
                    netmon.add_named_time(
                        "last_push_time",
                        application_name + sensor_name,
                        time.time(),
                    )
    except error.HTTPError as e:
        if isinstance(entity, Observation):
            # a failed observation is fine ...
            debug_logger.warning(f"{e} {e.read()}")
            netmon.add_named_count("push_fail", application_name, 1)
            return {}
        else:
            # ... a failed non-observation object is not!
            raise e

    if CONTAINER_ENVIRONMENT:
        new_object_url = new_object_url.replace("localhost", "web")

    with request.urlopen(new_object_url) as response:
        response = json.loads(response.read())

    iot_links = {
        str.lower(link_name + "_url"): response[link_name + "@iot.navigationLink"]
        for link_name in expected_links
    }
    iot_links.update({"self_url": new_object_url})
    return iot_links


def make_frost_datastream(
    entity: "Datastream",
    sensor_id: int,
    thing_id: int,
    observed_property_id: int,
) -> None:
    frost_endpoint = os.getenv("FROST_ENDPOINT") or FROST_ENDPOINT_DEFAULT
    if check_existing_object(entity, CONTAINER_ENVIRONMENT):
        logger.info(f"Creation Skipped: {entity.st_type} {entity.name} already exists.")
        return None
    url = frost_endpoint + "/Datastreams"
    data = entity.model_dump(exclude={"iot_links", "id", "st_type"})
    links = {
        "Thing": {"@iot.id": thing_id},
        "Sensor": {"@iot.id": sensor_id},
        "ObservedProperty": {"@iot.id": observed_property_id},
    }
    data.update(links)
    data = json.dumps(data).encode()
    post_request = request.Request(url=url, data=data, method="POST")
    post_request.add_header("Content-Type", "application/json")
    post_request.add_header("Authorization", f"Basic {FROST_CREDENTIALS}")
    try:
        with request.urlopen(post_request) as response:
            new_object_url = response.getheader(
                "Location"
            )  # "Location" does not refer to a SensorThings Location
            logger.info(f"New Datastream created at {new_object_url}")
    except error.HTTPError as e:
        logger.critical(f"{e} {e.read()}")


def find_datastream_url(
    sensor_name: str,
    datastream_name: ObservedProperties,
    container_environment: bool,
) -> UrlStr:
    """Query the FROST server, find the push URL associated with the passed sensor_name and datastream name."""
    frost_sensors = filter_query(
        entity="/Sensors",
        filter_string=f"name eq '{sensor_name}'",
        url=None,
        container_environment=container_environment,
    )
    try:
        # url to datastreams associated with sensor.
        # TODO: better handling of unfound datastreams.
        logger.debug(f"{sensor_name=}, {datastream_name=}")
        sensor_datastream_url = frost_sensors["value"][0][
            "Datastreams@iot.navigationLink"
        ]
        # query with the datastreams url to return the datastream with
        # the same name as <datastream_name>
        datastream = filter_query(
            entity=None,
            filter_string=f"name eq '{datastream_name}'",
            url=sensor_datastream_url,
            container_environment=CONTAINER_ENVIRONMENT,
        )

        push_link = datastream["value"][0]["Observations@iot.navigationLink"]
        return push_link
    except IndexError as e:
        if "list index out of range" in str(e):
            logger.warning(
                f"Datastream {datastream_name} not found for " + f"{sensor_name}."
            )
            return ""


def observation_to_sensor_trace(url: str, return_url: bool = False) -> str | None:
    """Return name or URL of sensor which generated an observation."""
    if not re.search(r"/Observations\(\d+\)$", url):
        logger.warning(
            "Did not find a datastream associated with this observation."
            + f"Check the URL passed: {url}"
        )
        return None
    if CONTAINER_ENVIRONMENT:
        url = url.replace("localhost", "web")

    try:
        with request.urlopen(url) as response:
            datastream_url = json.loads(response.read())[
                "Datastream@iot.navigationLink"
            ]
        if CONTAINER_ENVIRONMENT:
            datastream_url = datastream_url.replace("localhost", "web")

        with request.urlopen(datastream_url) as response:
            sensor_url = json.loads(response.read())["Sensor@iot.navigationLink"]
            if CONTAINER_ENVIRONMENT:
                sensor_url = sensor_url.replace("localhost", "web")

            if return_url:
                return sensor_url
        with request.urlopen(sensor_url) as response:
            return json.loads(response.read())["name"]

    except error.URLError as e:
        logger.warning(
            f"Unable to map sensor to created observation. {url=} URL Error: {e}"
        )
    except KeyError as e:
        logger.warning(f"Missing expected key: {e}")

def frost_observation_upload(
    sensor_name: SensorID,
    observation_set: Tuple[Observation, ObservedProperties],
    app_name: str | None = None,
) -> None:
    """Upload an observation set to the FROST server."""
    observation, datastream_name = observation_set
    upload_success = False
    push_link = find_datastream_url(
        sensor_name, datastream_name, CONTAINER_ENVIRONMENT
    )
    if not push_link:
        raise FrostUploadFailure(
                "Unable to upload payload: no datastream URL found: "
                f"{sensor_name=} {datastream_name=}"
            )
    try:
        make_frost_object(observation, push_link, app_name)
        upload_success = True
    except Exception as e:
        raise FrostUploadFailure(
                f"Unable to upload payload: {e}"
            )
    if not upload_success:
        app_name = app_name or ""
        netmon.add_named_count("push_fail", app_name, 1)
    return None
