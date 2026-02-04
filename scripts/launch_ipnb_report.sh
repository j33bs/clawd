#!/bin/bash

# Script to launch the IPNB research report in a separate window

REPORT_PATH="./COMPREHENSIVE_IPNB_RESEARCH_REPORT.md"

# Check if the file exists
if [ ! -f "$REPORT_PATH" ]; then
    echo "Error: Report file not found at $REPORT_PATH"
    exit 1
fi

echo "Opening IPNB Research Report..."

# Detect the operating system and open accordingly
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open "$REPORT_PATH"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v xdg-open &> /dev/null; then
        xdg-open "$REPORT_PATH"
    else
        echo "Please install xdg-open or manually open the file: $REPORT_PATH"
    fi
else
    echo "Unsupported OS. Please manually open the file: $REPORT_PATH"
fi

echo "Report launched in a separate window."