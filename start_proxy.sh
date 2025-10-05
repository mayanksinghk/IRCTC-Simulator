#!/bin/bash
# Filename: run_all.sh

# Change these paths if needed
SERVER_PY="./server.py"
PROXY_PY="./proxy.py"
CLIENT_PY="./client.py"

# Launch server
gnome-terminal -- bash -c "echo 'Starting Server'; python3 $SERVER_PY; exec bash"

# Wait a second to make sure server is up
sleep 1

# Launch proxy
gnome-terminal -- bash -c "echo 'Starting Proxy'; python3 $PROXY_PY; exec bash"

# Wait a second to make sure proxy is up
sleep 1

# Launch client
gnome-terminal -- bash -c "echo 'Starting Client'; python3 $CLIENT_PY; exec bash"
