# System Monitor Dashboard

## Overview
Real-time status of all automated systems in the Clawdbot architecture.

## System Status

### Memory Management System
- **Status**: ✅ Active
- **Last Check**: 2026-01-29 06:35:42
- **Daily File**: `/memory/2026-01-29.md` (updated)
- **Heartbeat State**: `/memory/heartbeat-state.json` (monitored)
- **Habits System**: `/memory/habits.json` (initialized)

### Job System
- **Status**: ✅ Active
- **Jobs Directory**: `/jobs/` (created)
- **Queue File**: `/jobs/queue.json` (initialized)
- **Pending Jobs**: 0
- **Completed Jobs**: 0
- **Failed Jobs**: 0

### Cognitive Load Routing
- **Status**: ✅ Active
- **Config File**: `/cognitive_config.json` (created)
- **Tiers Active**: 4 (Light, Moderate, Heavy, Critical)
- **Intents Tracked**: 12 categories
- **Context Compaction**: Enabled

### Self-Improvement System
- **Status**: ✅ Active
- **Log File**: `/memory/improvement_log.json` (initialized)
- **Research Categories**: 6 (productivity, communication, learning, health, creativity, relationships)
- **Last Research**: 2026-01-29 06:35:42
- **Auto-Apply Threshold**: 0.8

### Therapeutic Framework
- **Status**: ✅ Active
- **Tracking File**: `/memory/therapeutic_tracking.json` (created)
- **IPNB Applications**: Tracked
- **ACT Integrations**: Tracked
- **Emotion Regulation**: Tracked

### Task Scheduler
- **Status**: ✅ Active
- **Cron Config**: `/cron_jobs.json` (created)
- **Scheduled Jobs**: 3
- **Daily Memory Maintenance**: 0 2 * * * (2 AM daily)
- **Weekly Improvement Research**: 30 10 * * 1 (Mon 10:30 AM)
- **Weekly Therapeutic Review**: 0 9 * * 0 (Sun 9 AM)

## Active Scripts
- `memory_daily_review.sh` - Daily memory maintenance
- `self_improvement_research.sh` - Downtime research tasks
- `review_therapeutic_updates.js` - Weekly therapeutic reviews
- `setup_automated_systems.js` - System initialization

## Key Files & Directories
- **Memory**: `/memory/` - Daily logs and state tracking
- **Jobs**: `/jobs/` - Task management and execution logs
- **Configs**: `/cognitive_config.json`, `/cron_jobs.json` - System settings
- **Reports**: `/memory/system_setup_report_*.json` - System health reports

## Monitoring Commands
- Check system status: `node setup_automated_systems.js`
- Run memory review: `./memory_daily_review.sh`
- Run improvement research: `./self_improvement_research.sh`
- View today's log: `cat /memory/$(date +%Y-%m-%d).md`
- Check heartbeat state: `cat /memory/heartbeat-state.json`

## Next Steps
1. Monitor daily memory files for automated entries
2. Review system reports in `/memory/` directory
3. Adjust cron schedules in `/cron_jobs.json` as needed
4. Add new automated tasks based on evolving needs
5. Regular system health checks using monitoring commands

## Troubleshooting
- If memory maintenance stops: Check `memory_daily_review.sh` permissions
- If research tasks fail: Verify system downtime detection
- If jobs don't execute: Check cron configuration and system resources
- For general issues: Review system setup report in `/memory/`

---
*Dashboard last updated: 2026-01-29 06:35:42*