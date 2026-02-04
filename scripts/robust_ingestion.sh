#!/bin/bash

# Robust Ingestion Script
# Handles file locks and other access issues gracefully

INBOX_DIR="$HOME/Desktop/pdfs_inbox"
CORPUS_DIR="./pdf"
MANIFEST_DIR="./pdf/_manifest"

# Create required directories
mkdir -p "$CORPUS_DIR" "$MANIFEST_DIR"

echo "Starting robust ingestion at $(date)"

# Find all PDF files in the INBOX directory
for pdf_file in "$INBOX_DIR"/*.pdf; do
    if [ -f "$pdf_file" ]; then
        filename=$(basename "$pdf_file")
        target_path="$CORPUS_DIR/$filename"
        
        if [ -f "$target_path" ]; then
            echo "File $filename already exists in corpus, skipping..."
        else
            echo "Attempting to process: $filename"
            
            # Try to determine if file is accessible
            if [ -r "$pdf_file" ]; then
                # File is readable, check if it's a valid PDF
                # Use a different approach that might handle locks better
                if dd if="$pdf_file" bs=1024 count=1 2>/dev/null | head -c 4 | grep -q "%PDF"; then
                    echo "Valid PDF header detected for $filename"
                    
                    # Attempt to copy the file (try copy first, then move if copy works)
                    if cp "$pdf_file" "$CORPUS_DIR/"; then
                        echo "Successfully copied $filename to corpus"
                        
                        # Record provenance information
                        file_size=$(stat -f%z "$pdf_file" 2>/dev/null || stat -c%s "$pdf_file" 2>/dev/null)
                        file_hash=$(shasum -a 256 "$pdf_file" 2>/dev/null | cut -d ' ' -f 1)
                        
                        echo "$(date): INGESTED - $filename (SHA256: $file_hash, Size: $file_size bytes, Source: $INBOX_DIR)" >> "$MANIFEST_DIR/ingestion_log.txt"
                        echo "$(date): Added $filename to authorized corpus for verification and analysis" >> "$MANIFEST_DIR/process_log.txt"
                        
                        # Optionally remove from inbox after successful copy
                        # Uncomment the next line if you want to remove the original
                        # rm "$pdf_file"
                    else
                        echo "Failed to copy $filename - may be locked or in use"
                        echo "$(date): FAILED TO COPY - $filename (may be locked or in use)" >> "$MANIFEST_DIR/ingestion_log.txt"
                    fi
                else
                    echo "File $filename is not a valid PDF, skipping..."
                    echo "$(date): INVALID PDF - $filename skipped (no PDF header)" >> "$MANIFEST_DIR/ingestion_log.txt"
                fi
            else
                echo "File $filename is not readable, may be locked by another process"
                echo "$(date): LOCKED FILE - $filename (not readable)" >> "$MANIFEST_DIR/ingestion_log.txt"
            fi
        fi
    fi
done

echo "Robust ingestion complete at $(date)"