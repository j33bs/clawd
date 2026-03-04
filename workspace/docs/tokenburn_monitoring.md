# Token Burn Monitoring

## Daily Summary Script
- Script path: `/Users/heathyeager/clawd/tools/run_daily_token_burn_summary.sh`
- Input log: `/Users/heathyeager/clawd/workspace/logs/token_usage.jsonl`
- Output report: `/Users/heathyeager/clawd/workspace/audit/token_burn_daily_<YYYY-MM-DD>.md`

## Gateway Cron Job
- Name: `Token Burn Daily Summary`
- Job ID: `c2d8c98d-1a05-44b7-a516-5456454a7754`
- Schedule: daily at `09:00` (`Australia/Brisbane`)
- Session mode: `isolated`
- Delivery mode: `none`

## Manual Run
```bash
bash /Users/heathyeager/clawd/tools/run_daily_token_burn_summary.sh
```

## Trigger via Gateway Cron
```bash
openclaw cron run c2d8c98d-1a05-44b7-a516-5456454a7754
openclaw cron runs --id c2d8c98d-1a05-44b7-a516-5456454a7754
```

## Disable/Remove
```bash
openclaw cron disable c2d8c98d-1a05-44b7-a516-5456454a7754
# or remove entirely
openclaw cron remove c2d8c98d-1a05-44b7-a516-5456454a7754
```

## Re-enable
```bash
openclaw cron enable c2d8c98d-1a05-44b7-a516-5456454a7754
```
