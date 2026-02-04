#!/bin/bash

# Daily Memory Review Script
# Executes daily memory maintenance tasks with enhanced functionality

echo "🔍 Starting daily memory review at $(date)"

# Set workspace directory
WORKSPACE_DIR="/Users/heathyeager/clawd"
MEMORY_DIR="$WORKSPACE_DIR/memory"

# Create today's memory file if it doesn't exist
TODAY_FILE="$MEMORY_DIR/$(date +%Y-%m-%d).md"
if [ ! -f "$TODAY_FILE" ]; then
    echo "# Memory - $(date +%Y-%m-%d)" > "$TODAY_FILE"
    echo "" >> "$TODAY_FILE"
    echo "## Today's Activities" >> "$TODAY_FILE"
    echo "- Daily memory file created" >> "$TODAY_FILE"
    echo "" >> "$TODAY_FILE"
    echo "## Tasks Completed" >> "$TODAY_FILE"
    echo "- [ ] Memory review tasks" >> "$TODAY_FILE"
    echo "" >> "$TODAY_FILE"
    echo "## System Status" >> "$TODAY_FILE"
    echo "- Automated systems operational" >> "$TODAY_FILE"
    echo "" >> "$TODAY_FILE"
fi

# Update heartbeat state with enhanced tracking
HEARTBEAT_STATE="$MEMORY_DIR/heartbeat-state.json"
TIMESTAMP=$(date +%s)

if [ -f "$HEARTBEAT_STATE" ]; then
    # More robust JSON update using Python if jq not available
    if command -v jq >/dev/null 2>&1; then
        jq --arg ts "$TIMESTAMP" '
            .lastChecks.memoryReview = ($ts | tonumber) |
            .lastChecks.memoryCuration = ($ts | tonumber) |
            .lastChecks.dailyReview = ($ts | tonumber)
        ' "$HEARTBEAT_STATE" > "$HEARTBEAT_STATE.tmp" && mv "$HEARTBEAT_STATE.tmp" "$HEARTBEAT_STATE"
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c "
import json
import sys
with open('$HEARTBEAT_STATE', 'r') as f:
    data = json.load(f)
data['lastChecks']['memoryReview'] = $TIMESTAMP
data['lastChecks']['memoryCuration'] = $TIMESTAMP
data['lastChecks']['dailyReview'] = $TIMESTAMP
with open('$HEARTBEAT_STATE.tmp', 'w') as f:
    json.dump(data, f, indent=2)
"
        mv "$HEARTBEAT_STATE.tmp" "$HEARTBEAT_STATE"
    else
        # Simple timestamp update without JSON validation
        sed -i.bak "s/\"memoryReview\": [0-9]*/\"memoryReview\": $TIMESTAMP/" "$HEARTBEAT_STATE"
    fi
else
    cat > "$HEARTBEAT_STATE" << EOF
{
  "lastChecks": {
    "memoryReview": $TIMESTAMP,
    "memoryCuration": $TIMESTAMP,
    "dailyReview": $TIMESTAMP
  },
  "maintenanceSchedule": {
    "daily": ["reviewRecentLogs"],
    "weekly": ["curateLongTermMemory"],
    "monthly": ["auditMemoryFiles"]
  }
}
EOF
fi

# Advanced analysis of recent memory files for long-term promotion
echo "📚 Analyzing recent memory files for long-term promotion..."

# Define key terms that indicate important information
KEY_TERMS="Decision|Important|Note|Key|Significant|Lesson|Learning|Insight|Discovery|Realization|Breakthrough|Understanding|Achievement|Goal|Project|Idea|Concept|Method|Strategy|Approach|Framework|Model|Theory|Practice|Skill|Knowledge|Wisdom|Value|Belief|Experience|Reflection|Observation|Pattern|Connection|Relationship|Insight|Growth|Development|Change|Improvement|Success|Failure|Challenge|Opportunity|Risk|Benefit|Outcome|Result|Impact|Effect|Cause|Reason|Purpose|Meaning|Truth|Fact|Data|Information|Knowledge|Wisdom"

RECENT_FILES=$(find $MEMORY_DIR -name "*.md" -type f -mtime -7 | sort -r)
IMPORTANT_ITEMS_FOUND=0

for file in $RECENT_FILES; do
    if [[ $file != *"$(date +%Y-%m-%d)"* ]]; then
        echo "  Reviewing $file for important information..."
        
        # Count occurrences of key terms
        COUNT=$(grep -E -i -o "$KEY_TERMS" "$file" | wc -l)
        if [ "$COUNT" -gt 0 ]; then
            echo "    Found $COUNT important items"
            IMPORTANT_ITEMS_FOUND=$((IMPORTANT_ITEMS_FOUND + COUNT))
            
            # Extract lines with key terms
            grep -E -i -n "$KEY_TERMS" "$file" | head -5
        fi
    fi
done

# Check if MEMORY.md needs updating based on recent activities
MEMORY_MD="$WORKSPACE_DIR/MEMORY.md"
if [ -f "$MEMORY_MD" ]; then
    echo "🔄 Checking MEMORY.md for updates needed..."
    
    # Extract recent projects from recent files
    RECENT_PROJECTS=$(find $MEMORY_DIR -name "*.md" -type f -mtime -2 -exec grep -i -o -h "project.*" {} \; | wc -l)
    if [ "$RECENT_PROJECTS" -gt 0 ]; then
        echo "  📋 Detected $RECENT_PROJECTS potential new projects in recent logs"
    fi
    
    # Extract recent learnings from recent files
    RECENT_LEARNINGS=$(find $MEMORY_DIR -name "*.md" -type f -mtime -2 -exec grep -i -l "learn\|insight\|discovery\|understanding\|realization" {} \; | wc -l)
    if [ "$RECENT_LEARNINGS" -gt 0 ]; then
        echo "  💡 Found $RECENT_LEARNINGS files with recent learnings that might need to be added to long-term memory"
    fi
    
    # Check for therapeutic content
    THERAPEUTIC_CONTENT=$(find $MEMORY_DIR -name "*.md" -type f -mtime -2 -exec grep -i -l "therapeutic\|ipnb\|act\|emotional regulation\|healing\|trauma\|therapy\|counseling" {} \; | wc -l)
    if [ "$THERAPEUTIC_CONTENT" -gt 0 ]; then
        echo "  🧠 Found $THERAPEUTIC_CONTENT therapeutic-related items for potential long-term memory inclusion"
    fi
fi

# Clean up temporary notes that are no longer needed
echo "🗑️  Looking for temporary notes to clean up..."
TEMP_NOTES=$(find $MEMORY_DIR -name "*temp*" -o -name "*draft*" -o -name "*tmp*" -o -name "*backup*" 2>/dev/null | wc -l)
if [ "$TEMP_NOTES" -gt 0 ]; then
    echo "  Found $TEMP_NOTES temporary files that may need review"
    TEMP_FILES_LIST=$(find $MEMORY_DIR -name "*temp*" -o -name "*draft*" -o -name "*tmp*" -o -name "*backup*" 2>/dev/null)
    for temp_file in $TEMP_FILES_LIST; do
        echo "    - $temp_file (size: $(du -h "$temp_file" | cut -f1))"
    done
fi

# Perform weekly curation tasks if it's Sunday
DAY_OF_WEEK=$(date +%u)  # 1=Monday, 7=Sunday
if [ "$DAY_OF_WEEK" -eq 7 ]; then
    echo "📅 Performing weekly memory curation tasks..."
    
    # Find files from the past week to consider for long-term memory
    WEEKLY_FILES=$(find $MEMORY_DIR -name "*.md" -type f -mtime -7 | grep -v "$(date +%Y-%m-%d)" | wc -l)
    echo "  Analyzed $WEEKLY_FILES files from the past week"
    
    # Update weekly metrics in heartbeat state
    if command -v jq >/dev/null 2>&1; then
        jq --arg weekly_files "$WEEKLY_FILES" --arg important_items "$IMPORTANT_ITEMS_FOUND" '
            .weeklyMetrics = (.weeklyMetrics // {}) |
            .weeklyMetrics.filesReviewed = ($weekly_files | tonumber) |
            .weeklyMetrics.importantItemsFound = ($important_items | tonumber) |
            .weeklyMetrics.lastWeeklyReview = '$TIMESTAMP'
        ' "$HEARTBEAT_STATE" > "$HEARTBEAT_STATE.tmp" && mv "$HEARTBEAT_STATE.tmp" "$HEARTBEAT_STATE"
    fi
fi

# Generate detailed summary
echo ""
echo "✅ Daily memory review completed at $(date)"
echo "📁 Workspace: $WORKSPACE_DIR"
echo "💾 Memory directory: $MEMORY_DIR"
echo "📝 Today's file: $TODAY_FILE"
echo ""

# Count total memory files
TOTAL_FILES=$(find $MEMORY_DIR -name "*.md" -type f | wc -l)
echo "📊 Total memory files in system: $TOTAL_FILES"

# Count total word count in recent memory
RECENT_WORD_COUNT=$(find $MEMORY_DIR -name "*.md" -type f -mtime -7 -exec cat {} \; | wc -w)
echo "📈 Words in recent memory (last 7 days): $RECENT_WORD_COUNT"

# Count total storage used
MEMORY_SIZE=$(du -sh $MEMORY_DIR | cut -f1)
echo "📦 Memory directory size: $MEMORY_SIZE"

# Performance metrics
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - TIMESTAMP))
echo "⏱️  Execution time: ${ELAPSED}s"

echo ""
echo "🎯 Next recommended actions:"
echo "   - Review important items found for long-term memory promotion"
echo "   - Update MEMORY.md with significant insights from recent activities"
echo "   - Archive temporary files that are no longer needed"
echo ""
echo "🔄 Memory maintenance cycle complete."