#!/bin/sh
set -e

apk add --no-cache jq

password_file=/mosquitto/config/passwords.txt
acl_file=/mosquitto/config/acl.txt
rm -f "$password_file" "$acl_file"

secret_file=/run/secrets/mqtt_credentials
if [ -f "$secret_file" ]; then
    echo "Generating Mosquitto users and ACLs from secret JSON..."

    # Loop over each user object
    jq -c '.[]' "$secret_file" | while read -r user; do
        username=$(echo "$user" | jq -r '.username')
        password=$(echo "$user" | jq -r '.password')

        mosquitto_passwd -b -c "$password_file" "$username" "$password"

        echo "user $username" >> "$acl_file"

        echo "$user" | jq -c '.topics[]' | while read -r topic_obj; do
            topic_name=$(echo "$topic_obj" | jq -r '.name')
            perm=$(echo "$topic_obj" | jq -r '.perm')
            echo "topic $perm $topic_name" >> "$acl_file"
        done
    done
else
    echo "No MQTT users secret found at $secret_file"
fi

chown mosquitto:mosquitto "$password_file" "$acl_file"

echo "Starting Mosquitto..."
exec mosquitto -c /mosquitto/config/mosquitto.conf
