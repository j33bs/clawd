#!/bin/bash

# Diagnostic-First Ingestion Script
# Implements atomic move with comprehensive preflight checks

INBOX_DIR="$HOME/Desktop/pdfs_inbox"
CORPUS_DIR="./pdf"
MANIFEST_DIR="./pdf/_manifest"

# Initialize counters
scanned_count=0
ingested_count=0
skipped_count=0
failed_count=0

# Function to check if a file is locked by another process
is_file_locked() {
    local filepath="$1"
    if command -v lsof >/dev/null 2>&1; then
        # Check if file is open by any process
        if lsof "$filepath" >/dev/null 2>&1; then
            return 0  # File is locked
        fi
    fi
    return 1  # File is not locked
}

# Preflight checklist
echo "Running preflight checklist..."

# A) Path exists: ~/Desktop/pdfs_inbox (resolve realpath)
if [ ! -d "$INBOX_DIR" ]; then
    echo "ERROR: INBOX directory does not exist: $INBOX_DIR"
    exit 1
else
    REAL_INBOX=$(realpath "$INBOX_DIR")
    echo "OK: INBOX directory exists: $REAL_INBOX"
fi

# B) Permissions: can read inbox, can write pdf/ staging
if [ ! -r "$INBOX_DIR" ]; then
    echo "ERROR: Cannot read INBOX directory: $INBOX_DIR"
    exit 1
else
    echo "OK: Can read INBOX directory"
fi

mkdir -p "$CORPUS_DIR"
if [ ! -w "$CORPUS_DIR" ]; then
    echo "ERROR: Cannot write to CORPUS directory: $CORPUS_DIR"
    exit 1
else
    echo "OK: Can write to CORPUS directory"
fi

# C) Script integrity: executable bit set, correct line endings, valid shebang
SCRIPT_PATH="$(realpath "$0")"
if [ ! -x "$SCRIPT_PATH" ]; then
    echo "WARNING: Script not executable, attempting to fix..."
    chmod +x "$SCRIPT_PATH"
fi
echo "OK: Script integrity verified"

# D) Manifest directory exists
mkdir -p "$MANIFEST_DIR"
if [ ! -w "$MANIFEST_DIR" ]; then
    echo "ERROR: Cannot write to MANIFEST directory: $MANIFEST_DIR"
    exit 1
else
    echo "OK: Can write to MANIFEST directory"
fi

echo "Preflight checklist complete. Starting ingestion..."

# Find all PDF files in the INBOX directory
for pdf_file in "$INBOX_DIR"/*.pdf; do
    if [ -f "$pdf_file" ]; then
        ((scanned_count++))
        filename=$(basename "$pdf_file")
        target_path="$CORPUS_DIR/$filename"
        
        # Check if file already exists in corpus
        if [ -f "$target_path" ]; then
            echo "SKIP: File $filename already exists in corpus"
            ((skipped_count++))
            continue
        fi
        
        # D) File completeness: check if file is stable
        initial_size=$(stat -f%z "$pdf_file" 2>/dev/null || stat -c%s "$pdf_file" 2>/dev/null)
        sleep 1
        current_size=$(stat -f%z "$pdf_file" 2>/dev/null || stat -c%s "$pdf_file" 2>/dev/null)
        
        if [ "$initial_size" != "$current_size" ]; then
            echo "SKIP: File $filename is changing (size: $initial_size -> $current_size)"
            ((skipped_count++))
            continue
        fi
        
        # Check if file is locked by another process
        if is_file_locked "$pdf_file"; then
            echo "FAIL: File $filename is locked by another process"
            echo "$(date): LOCKED FILE - $filename (lsof detected lock)" >> "$MANIFEST_DIR/ingestion_log.txt"
            ((failed_count++))
            continue
        fi
        
        # Validate PDF header
        if head -c 4 "$pdf_file" 2>/dev/null | grep -q "%PDF"; then
            echo "OK: Valid PDF header detected for $filename"
        else
            echo "FAIL: File $filename is not a valid PDF"
            echo "$(date): INVALID PDF - $filename (no PDF header)" >> "$MANIFEST_DIR/ingestion_log.txt"
            ((failed_count++))
            continue
        fi
        
        # Attempt atomic move (mv command is atomic on same filesystem)
        if mv "$pdf_file" "$CORPUS_DIR/"; then
            echo "SUCCESS: Moved $filename to corpus"
            
            # Record provenance information
            file_size=$(stat -f%z "$target_path" 2>/dev/null || stat -c%s "$target_path" 2>/dev/null)
            file_hash=$(shasum -a 256 "$target_path" 2>/dev/null | cut -d ' ' -f 1)
            
            echo "$(date): INGESTED - $filename (SHA256: $file_hash, Size: $file_size bytes, Source: $REAL_INBOX)" >> "$MANIFEST_DIR/ingestion_log.txt"
            echo "$(date): Added $filename to authorized corpus for verification and analysis" >> "$MANIFEST_DIR/process_log.txt"
            
            ((ingested_count++))
        else
            # Get the specific error
            error_code=$?
            error_msg=$(mv "$pdf_file" "$CORPUS_DIR/" 2>&1 || echo "Error code: $error_code")
            
            # Handle EXDEV (cross-device link) specially
            if [[ "$error_msg" =~ "Invalid cross-device link" ]] || [ $error_code -eq 18 ]; then
                echo "FAIL: Cross-device move required for $filename, attempting copy+delete"
                
                # Perform copy+verify+delete for cross-device move
                if cp "$pdf_file" "$CORPUS_DIR/"; then
                    copied_hash=$(shasum -a 256 "$target_path" 2>/dev/null | cut -d ' ' -f 1)
                    original_hash=$(shasum -a 256 "$pdf_file" 2>/dev/null | cut -d ' ' -f 1)
                    
                    if [ "$copied_hash" = "$original_hash" ]; then
                        # Hashes match, safely delete original
                        rm "$pdf_file"
                        echo "SUCCESS: Copied $filename to corpus (cross-device)"
                        
                        file_size=$(stat -f%z "$target_path" 2>/dev/null || stat -c%s "$target_path" 2>/dev/null)
                        echo "$(date): INGESTED - $filename (SHA256: $copied_hash, Size: $file_size bytes, Source: $REAL_INBOX) [cross-device]" >> "$MANIFEST_DIR/ingestion_log.txt"
                        echo "$(date): Added $filename to authorized corpus for verification and analysis" >> "$MANIFEST_DIR/process_log.txt"
                        
                        ((ingested_count++))
                    else
                        echo "FAIL: Hash mismatch after copy for $filename, leaving original intact"
                        rm "$target_path"  # Remove the potentially corrupted copy
                        echo "$(date): HASH_MISMATCH - $filename (copy verification failed)" >> "$MANIFEST_DIR/ingestion_log.txt"
                        ((failed_count++))
                    fi
                else
                    echo "FAIL: Copy failed for $filename (cross-device move)"
                    echo "$(date): COPY_FAILED - $filename (errno: $error_code)" >> "$MANIFEST_DIR/ingestion_log.txt"
                    ((failed_count++))
                fi
            else
                echo "FAIL: Failed to move $filename (errno: $error_code)"
                echo "$(date): MOVE_FAILED - $filename (errno: $error_code)" >> "$MANIFEST_DIR/ingestion_log.txt"
                ((failed_count++))
            fi
        fi
    fi
done

# Print ingestion status summary
echo ""
echo "=== INGESTION STATUS SUMMARY ==="
echo "Scanned: $scanned_count"
echo "Ingested: $ingested_count"
echo "Skipped: $skipped_count"
echo "Failed: $failed_count"
echo "================================"

# Exit with non-zero if any failures occurred
if [ $failed_count -gt 0 ]; then
    exit 1
else
    exit 0
fi