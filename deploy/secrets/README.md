# ST-Utils Docker Secrets

Secrets (API keys, database passwords, users, etc.,) are managed by `Docker`
through the [`secrets`](https://docs.docker.com/compose/how-tos/use-secrets/)
mechanisim. All files in this directory will be ignored by `git`, excluding this
`README`.

Every secret added in this directory should live in its own file, i.e., one file
per secret. The following secrets are required:

| Secret Variable | Filename | Description |
| ----------------|----------|-------------|
| FROST_USER      | FROST_USER.txt | ......|
| POSTGRES_USER   | POSTGRES_USER.txt | The user of the persistentce database, used by both the `database` and `web` containers. |
| POSTGRES_PASSWORD | POSTGRES_PASSWORD | 
persistence_db_username = "sta-manager"
FROST_PASSWORD = "!0000st"
POSTGRES_PASSWORD = "!0000st"
persistence_db_password = "!0000st"
auth_db_password = "!0000st"
NETATMO_CREDENTIALS = {"tudelft-dt": {"CLIENT_ID": "676405218c33a313640f0070", "CLIENT_SECRET": "WegIHcAL6viJvNRlOhOUveE33oaEaLA8DnzPGMdeBO", "REFRESH_TOKEN": "676404d415a6db50d5091272|f3ee2f719d3c7b90bc474f2dbecfafac"}}
TTS_CREDENTIALS = {"multicare-bucharest@ttn":{"API_KEY":"NNSXS.U7DP7H62SCXI7K5OZ7KLPSXWD2HXUGKK2OF4Y7A.PBDVYRPU3KXJRIT5DGOPT2DM7QO4RC6GWMFXOJ7JI733NLBG6B5A"},"multicare-acerra@ttn":{"API_KEY":"NNSXS.7GOG3C7RLU2LCBB4BHAWLCNE6GYPZKWEAX6P72Q.UNE7IOTHA75BI26NF4TDENXHBA5GXX6BZA4EJWHKZVU4GSFYB5FQ"}}
MQTT_USERS="sta-manager=!0000st"

