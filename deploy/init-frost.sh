#!/bin/sh

export persistence_db_password=$(cat /run/secrets/POSTGRES_PASSWORD)
/usr/local/tomcat/bin/catalina.sh run
