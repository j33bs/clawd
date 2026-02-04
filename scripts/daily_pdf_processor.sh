#!/bin/bash

# Daily PDF Processor
# Moves PDFs from desktop processing folder to authorized corpus

DESKTOP_PROCESSING_DIR="$HOME/Desktop/pdf_processing"
CORPUS_DIR="./pdf"

# Create corpus directory if it doesn't exist
mkdir -p "$CORPUS_DIR"

echo "Checking for PDFs in $DESKTOP_PROCESSING_DIR"

# Find all PDF files in the processing directory
for pdf_file in "$DESKTOP_PROCESSING_DIR"/*.pdf; do
    if [ -f "$pdf_file" ]; then
        filename=$(basename "$pdf_file")
        target_path="$CORPUS_DIR/$filename"
        
        if [ -f "$target_path" ]; then
            echo "File $filename already exists in corpus, skipping..."
        else
            echo "Processing: $filename"
            
            # Attempt to copy the file
            if cp "$pdf_file" "$CORPUS_DIR/"; then
                echo "  - Successfully copied to corpus: $target_path"
                
                # Optionally remove the original from desktop (commented out by default)
                # rm "$pdf_file"
                
                # Log the addition to the Quoted Papers Log
                echo "$(date): Added $filename to authorized corpus for verification and analysis" >> pdf/_manifest/process_log.txt 2>/dev/null || echo "Could not write to process log"
            else
                echo "  - Failed to copy $filename (may be locked or in use)"
            fi
        fi
    fi
done

echo "Daily PDF processing complete."