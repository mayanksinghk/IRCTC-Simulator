#!/bin/bash
# Filename: run_all.sh

# Change these paths if needed
APPSERVER="./app_server.py"
WEBSERVER="./web_server.py"
ADC="./adc.py"
CLIENT="./client.py"

# Generate ADC cert if not present
if [[ ! -f adc.crt || ! -f adc.key ]]; then
  echo "[*] Generating self-signed ADC certificate (adc.crt, adc.key)..."
  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout adc.key -out adc.crt \
    -subj "/CN=adc.local" \
    -addext "subjectAltName=DNS:adc.local,IP:127.0.0.1"
fi

# Launch application server
gnome-terminal -- bash -c "echo 'Starting Application Server'; python3 $APPSERVER; exec bash"
sleep 1

# Launch server
gnome-terminal -- bash -c "echo 'Starting Web Server'; python3 $WEBSERVER; exec bash"
sleep 1

# Launch proxy
gnome-terminal -- bash -c "echo 'Starting Proxy'; python3 $ADC; exec bash"
sleep 1

# Launch client
gnome-terminal -- bash -c "echo 'Starting Client'; python3 $CLIENT; exec bash"
