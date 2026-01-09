"""Expected datatypes such as credential file structures."""
#standard
#external
from pydantic import BaseModel, RootModel, Field
from typing import Dict, List, Literal
#internal

class AppCredentialStore(RootModel):
    """
    Dataclass representing the contents of application_credentials.json.

    Essentially, the application_credentials.json has the following structure:

        {
                <app_name_1:str>: {api_key: <api_key: str>},
                ...
                <app_name_n:str>: {api_key: <api_key: str>},
        }

    """
    class AppCredential(BaseModel):
        """An application credential found under application_credentials.json."""
        api_key: str = Field(..., min_length=1)

    root: Dict[str, AppCredential] = Field(..., min_length=1)

class FrostCredentials(BaseModel):
    frost_username: str = Field(..., min_length=1)
    frost_password: str = Field(..., min_length=1)

class PostgresCredentials(BaseModel):
    postgres_user: str = Field(..., min_length=1)
    postgres_password: str = Field(..., min_length=1)

class Topic(BaseModel):
    """A topic configuration for MQTT credentials."""
    name: str = Field(..., min_length=1)
    perm: Literal["read", "readwrite"] = Field(...)

class MqttCredentialStore(RootModel):
    """
    Dataclass representing the expected structure of the mqtt_credentials.json.

    Essentially, that file has the following structure:

    {
        "mqtt_user_1": {
            "username": "sta-manager",
            "password": "sta-manager",
            "topics": [
                {"name": "sensors/#", "perm": "readwrite"},
                {"name": "logs/#", "perm": "read"}
            ]
        },
        "mqtt_user_2": {
            "username": "sta-user",
            "password": "sta-user",
            "topics": [
                {"name": "sensors/#", "perm": "read"}
            ]
        }
    }
    """

    class MqttCredential(BaseModel):
        username: str = Field(..., min_length=1)
        password: str = Field(..., min_length=1)
        topics: List[Topic]

    root: Dict[str, MqttCredential] = Field(..., min_length=1)
