#!/bin/bash

PORT=8501

PIDS=$(lsof -ti tcp:$PORT)

if [ -z "$PIDS" ]; then
    echo "No app is currently running on port $PORT."
else
    echo "Stopping app running on port $PORT (PID: $PIDS)..."
    kill -9 $PIDS
    echo "App stopped."
fi

read -p "Press Enter to close..."