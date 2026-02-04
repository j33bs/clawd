#!/bin/bash

# Daily Ingestion Scheduler
# Sets up daily processing of PDFs from the INBOX directory

echo "Setting up daily PDF ingestion from INBOX directory..."
echo "INBOX directory: $HOME/Desktop/pdfs_inbox"
echo "Target corpus: ./pdf/"

# Create the directories if they don't exist
mkdir -p "$HOME/Desktop/pdfs_inbox"
mkdir -p ./pdf/_manifest

echo ""
echo "To schedule daily ingestion, run the following command in your terminal:"
echo "crontab -e"
echo "Then add this line:"
echo "0 9 * * * cd /Users/heathyeager/clawd && ./ingestion_watcher.sh >> ./pdf/_manifest/daily_log.txt 2>&1"
echo ""
echo "Important notes:"
echo "- Make sure any PDF viewers (Preview, Adobe Reader, etc.) are closed before running"
echo "- Place PDFs you want processed in ~/Desktop/pdfs_inbox/"
echo "- The system will automatically move them to the ./pdf/ directory for verification"
echo "- If a file fails to process, check if it's open in another application"
echo ""
echo "To manually run the ingestion now, use:"
echo "./ingestion_watcher.sh"