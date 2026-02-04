#!/bin/bash

# Script to launch the advanced IPNB research summary in a separate window

SUMMARY_PATH="./ADVANCED_IPNB_RESEARCH_SUMMARY.md"

# Check if the file exists
if [ ! -f "$SUMMARY_PATH" ]; then
    echo "Error: Advanced summary file not found at $SUMMARY_PATH"
    exit 1
fi

echo "Opening Advanced IPNB Research Summary..."

# Detect the operating system and open accordingly
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open "$SUMMARY_PATH"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v xdg-open &> /dev/null; then
        xdg-open "$SUMMARY_PATH"
    else
        echo "Please install xdg-open or manually open the file: $SUMMARY_PATH"
    fi
else
    echo "Unsupported OS. Please manually open the file: $SUMMARY_PATH"
fi

echo "Advanced summary launched in a separate window."