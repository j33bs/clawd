# Job System

## Overview
This system manages automated jobs with durable logs and artifacts. All actions are replayable from job inputs.

## Job Structure
Each job has:
- `id`: Unique identifier
- `status`: pending, running, success, failed, approved, rejected
- `type`: The type of job (email, calendar, notes, etc.)
- `inputs`: All inputs needed to replay the job
- `outputs`: Results from the job execution
- `artifacts`: Generated files or data
- `created_at`: Timestamp
- `completed_at`: Completion timestamp
- `logs`: Execution logs

## Status Definitions
- `pending`: Job queued for execution
- `running`: Currently executing
- `approved`: Awaiting approval for write operations
- `success`: Completed successfully
- `failed`: Failed during execution
- `rejected`: Approval rejected

## Sample Job Entry
```json
{
  "id": "job_abc123",
  "status": "success",
  "type": "email_digest",
  "inputs": {
    "date_range": "2025-01-30",
    "account": "primary"
  },
  "outputs": {
    "summary": "Found 5 unread emails",
    "digest_text": "..."
  },
  "artifacts": [
    "/artifacts/email_digest_2025-01-30.txt"
  ],
  "created_at": "2025-01-30T10:00:00Z",
  "completed_at": "2025-01-30T10:01:30Z",
  "logs": [
    {"timestamp": "2025-01-30T10:00:01Z", "level": "INFO", "message": "Job started"},
    {"timestamp": "2025-01-30T10:01:29Z", "level": "INFO", "message": "Completed successfully"}
  ]
}
```

## Job Storage
Jobs are stored in `/Users/heathyeager/clawd/jobs/` directory with files named `{job_id}.json`

## Error Handling
All errors are logged with full context for debugging and replayability.