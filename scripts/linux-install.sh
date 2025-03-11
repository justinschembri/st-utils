#!/bin/bash

# tomcat installation
sudo apt update && sudo apt upgrade -y
sudo apt install openjdk-17-jdk -y
cd /opt
sudo wget https://dlcdn.apache.org/tomcat/tomcat-10/v10.1.36/bin/apache-tomcat-10.1.36.tar.gz
sudo tar -xvzf apache-tomcat-10.1.36.tar.gz
sudo rm -rf apache-tomcat-10.1.36.tar.gz

# Can't really get this split user approach to work:

# sudo useradd -s /bin/false -g tomcat -d /opt/apache-tomcat-10.1.36 tomcat
# sudo usermod -aG tomcat jschembri
# sudo chown -R tomcat:tomcat /opt/apache-tomcat-10.1.36
# sudo chmod +x /opt/apache-tomcat-10.1.36/bin
# sudo nano /etc/profile.d/tomcat.sh

# sudo tee /etc/profile.d/tomcat.sh > /dev/null <<EOL
# export CATALINA_HOME=/opt/apache-tomcat-10.1.36
# export CATALINA_BASE=\$CATALINA_HOME
# export CATALINA_PID=\$CATALINA_HOME/temp/tomcat.pid
# export CATALINA_OPTS="-Xms512M -Xmx1024M -server -XX:+UseParallelGC"
# export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
# export PATH=\$CATALINA_HOME/bin:\$PATH
# EOL

# sudo chmod +x /etc/profile.d/tomcat.sh

# Create the systemd service file for Tomcat
sudo tee /etc/systemd/system/tomcat.service > /dev/null <<EOL
[Unit]
Description=Apache Tomcat Web Application 10.1.36 Container
After=network.target

[Service]
Type=forking
ExecStart=/opt/apache-tomcat-10.1.36/bin/startup.sh
ExecStop=/opt/apache-tomcat-10.1.36/bin/shutdown.sh
User=tomcat
Group=tomcat
Environment=CATALINA_HOME=/opt/apache-tomcat-10.1.36
Environment=CATALINA_BASE=\$CATALINA_HOME
Environment=JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
PIDFile=/opt/apache-tomcat-10.1.36/temp/tomcat.pid

[Install]
WantedBy=multi-user.target
EOL

# Reload systemd to apply the new service
sudo systemctl daemon-reload
sudo systemctl enable tomcat
sudo systemctl start tomcat

# Database setup
sudo apt install postgresql
sudo -u postgres psql
CREATE DATABASE sensorthings;
CREATE USER sensorthings WITH PASSWORD '<changeMe>';
GRANT ALL PRIVILEGES ON DATABASE sensorthings TO sensorthings;
\q


# FROST Installation
cd opt/apache-tomcat-10.1.36/webapps
sudo wget https://repo1.maven.org/maven2/de/fraunhofer/iosb/ilt/FROST-Server/FROST-Server.HTTP/2.5.3/FROST-Server.HTTP-2.5.3.war
