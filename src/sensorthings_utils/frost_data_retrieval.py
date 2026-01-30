"""Select, filter and download data from a FROST HTTP server."""

# standard
from dataclasses import dataclass, field
from abc import ABC
import time
import csv
from pathlib import Path
from typing import NamedTuple
from datetime import date
# external
import requests

# internal
from sensorthings_utils.sensor_things.core import Observation

@dataclass
class CuratedDataSet(ABC):
    """ABC for any dataset of observations which is curated."""

    metadata: NamedTuple
    observations: list[Observation] = field(default_factory=list)

    def to_csv(self, path: Path) -> None:
        with open(path, "w", newline="") as f:
            metadata_fieldnames = list(self.metadata._fields)
            observation_fieldnames = list(self.observations[0].__dict__.keys())
            fieldnames = metadata_fieldnames + observation_fieldnames
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            writer.writeheader()
            for obs in self.observations:
                row = self.metadata._asdict() | obs.__dict__
                writer.writerow(row)

    def add_observation(self, obs: Observation) -> None:
        self.observations.append(obs)

    def extend_observations(self, observations: list[Observation]) -> None:
        self.observations.extend(observations)


def _odata_escaping(s: str) -> str:
    """
    Quote a Python string for OData filter string literal: use single
    quotes, escape any single quote inside by doubling it
    (OData convention).
    """
    s = repr(s).replace("'", "").replace("\\", "").replace('"', "''")
    return s


def observations_link_from_thing(
    frost_url: str, thing_name: str, datastream_name: str
) -> str:
    "Return link to observations for a given Thing/Datastream combination."

    params = {"$filter": f"name eq '{thing_name}'"}
    response = requests.get(f"{frost_url}/Things", params)
    if not response.content:
        raise LookupError(f"Did not find Thing: {thing_name}")
    datastream_link = (
        response.json().get("value")[0].get("Datastreams@iot.navigationLink")
    )

    params = {"$filter": f"name eq '{datastream_name}'"}
    response = requests.get(datastream_link)
    if not response.content:
        raise LookupError(f"Did not find Thing: {thing_name}")
    observation_link = (
        response.json().get("value")[0].get("Observations@iot.navigationLink")
    )

    return observation_link


def fetch_observations(
    observations_url: str,
    iso_start_date: str | None = None,
    iso_end_date:  str | None = None,
    max_retries: int = 5,
    delay: float = 0.05,
) -> list[Observation]:
    """Recurse a set of observations until exhausted."""
    observations = []
    next_url = observations_url
    retries = 0
    while next_url:
        params = {"$select": "phenomenonTime, resultTime, result"}
        if iso_start_date:
            # ensure correct format implicitly:
            date.fromisoformat(iso_start_date)
            params["$filter"] = f"phenomenonTime ge {iso_start_date}T00:00Z"
            if iso_end_date:
                # ensure correct format implicitly:
                date.fromisoformat(iso_end_date)
                params["$filter"] = (
                        params["$filter"] + 
                        f"and phenomenonTime le {iso_end_date}T00:00Z"
                        )
        try:
            time.sleep(delay)
            response = requests.get(next_url, params)
            response.raise_for_status()
            data = response.json()

            if "value" not in data:
                raise LookupError("No content found.")

            for obs in data["value"]:
                observations.append(Observation(**obs))

            if "@iot.nextLink" in data:
                next_url = data["@iot.nextLink"]
            else:
                next_url = None

        except requests.exceptions.ConnectionError as e:
            if retries >= max_retries:
                raise e
            else:
                retries += 1
                time.sleep(1)

    return observations
