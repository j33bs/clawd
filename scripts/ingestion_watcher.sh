#!/bin/bash

# Ingestion Watcher Script
# Monitors INBOX directory and moves validated PDFs to corpus

INBOX_DIR="$HOME/Desktop/pdfs_inbox"
CORPUS_DIR="./pdf"
MANIFEST_DIR="./pdf/_manifest"

# Create required directories
mkdir -p "$CORPUS_DIR" "$MANIFEST_DIR"

echo "Starting ingestion watcher at $(date)"

# Find all PDF files in the INBOX directory
for pdf_file in "$INBOX_DIR"/*.pdf; do
    if [ -f "$pdf_file" ]; then
        filename=$(basename "$pdf_file")
        target_path="$CORPUS_DIR/$filename"
        
        if [ -f "$target_path" ]; then
            echo "File $filename already exists in corpus, skipping..."
        else
            echo "Processing: $filename"
            
            # Perform basic validation
            file_size=$(stat -f%z "$pdf_file" 2>/dev/null || stat -c%s "$pdf_file" 2>/dev/null)
            echo "File size: $file_size bytes"
            
            # Check if it's a valid PDF (basic check for PDF header)
            if head -c 4 "$pdf_file" | grep -q "%PDF"; then
                echo "Valid PDF header detected"
                
                # Generate hash for provenance tracking
                file_hash=$(shasum -a 256 "$pdf_file" | cut -d ' ' -f 1)
                
                # Attempt to move the file (instead of copy to avoid permission issues)
                if mv "$pdf_file" "$CORPUS_DIR/"; then
                    echo "Successfully moved $filename to corpus"
                    
                    # Record provenance information
                    echo "$(date): INGESTED - $filename (SHA256: $file_hash, Size: $file_size bytes, Source: $INBOX_DIR)" >> "$MANIFEST_DIR/ingestion_log.txt"
                    
                    # Add to process log
                    echo "$(date): Added $filename to authorized corpus for verification and analysis" >> "$MANIFEST_DIR/process_log.txt"
                else
                    echo "Failed to move $filename (may be locked, in use, or permission denied)"
                    echo "$(date): FAILED TO MOVE - $filename (Source: $INBOX_DIR)" >> "$MANIFEST_DIR/ingestion_log.txt"
                fi
            else
                echo "File $filename is not a valid PDF, skipping..."
                echo "$(date): INVALID PDF - $filename skipped (no PDF header)" >> "$MANIFEST_DIR/ingestion_log.txt"
            fi
        fi
    fi
done

echo "Ingestion watcher complete at $(date)"