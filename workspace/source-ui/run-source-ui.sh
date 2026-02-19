#!/bin/bash
#
# Source UI Launcher
# Usage: ./run-source-ui.sh [options]
#
# Options:
#   --port PORT    Port to run on (default: 18990)
#   --host HOST    Host to bind to (default: 127.0.0.1)
#   --daemon      Run as daemon in background
#   --stop        Stop running instance
#

PORT=18990
HOST="127.0.0.1"
DAEMON=false
APP_DIR="/home/jeebs/src/clawd/workspace/source-ui"
PID_FILE="/tmp/source-ui.pid"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --daemon)
            DAEMON=true
            shift
            ;;
        --stop)
            if [ -f "$PID_FILE" ]; then
                PID=$(cat "$PID_FILE")
                if kill -0 "$PID" 2>/dev/null; then
                    kill "$PID"
                    echo "Stopped Source UI (PID: $PID)"
                    rm -f "$PID_FILE"
                else
                    echo "Process not running"
                    rm -f "$PID_FILE"
                fi
            else
                # Try to find by process name
                PIDS=$(pgrep -f "source-ui/app.py")
                if [ -n "$PIDS" ]; then
                    kill $PIDS 2>/dev/null
                    echo "Stopped Source UI"
                fi
            fi
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Source UI already running on port $PORT (PID: $PID)"
        exit 0
    fi
fi

# Run
cd "$APP_DIR"

if [ "$DAEMON" = true ]; then
    nohup python3 "$APP_DIR/app.py" --port "$PORT" --host "$HOST" > /var/log/source-ui.log 2>&1 &
    echo $! > "$PID_FILE"
    echo "Started Source UI on $HOST:$PORT (PID: $(cat $PID_FILE))"
else
    echo "Starting Source UI on $HOST:$PORT..."
    python3 "$APP_DIR/app.py" --port "$PORT" --host "$HOST"
fi
