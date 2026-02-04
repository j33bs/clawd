#!/bin/bash

DESKTOP_PROCESSING_DIR="$HOME/Desktop/pdf_processing"
CORPUS_DIR="./pdf"

# Create corpus directory if it doesn't exist
mkdir -p "$CORPUS_DIR"

echo "Starting daily PDF processing at $(date)"

# Find all PDF files in the processing directory
for pdf_file in "$DESKTOP_PROCESSING_DIR"/*.pdf; do
    if [ -f "$pdf_file" ]; then
        filename=$(basename "$pdf_file")
        target_path="$CORPUS_DIR/$filename"
        
        if [ -f "$target_path" ]; then
            echo "File $filename already exists in corpus, skipping..."
        else
            echo "Processing: $filename"
            
            # Attempt to copy the file with error handling
            if cp "$pdf_file" "$CORPUS_DIR/" 2>/dev/null; then
                echo "Successfully copied $filename to corpus"
                
                # Create/update the Quoted Papers Log
                if [ ! -f "$CORPUS_DIR/_manifest/Quoted_Papers_Log.docx" ]; then
                    touch "$CORPUS_DIR/_manifest/Quoted_Papers_Log.docx"
                fi
                
                # Add entry to process log
                echo "$(date): Added $filename to authorized corpus for verification and analysis" >> "$CORPUS_DIR/_manifest/process_log.txt"
            else
                echo "Failed to copy $filename (may be locked, in use, or permission denied)"
            fi
        fi
    fi
done

echo "Daily PDF processing complete at $(date)"
