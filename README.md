# ITC Trading Pipeline System

This system implements a data-driven trading pipeline that processes information from Telegram channels to inform trading decisions.

## Architecture

### Data Ingestion
- `telethon_ingest.py`: Captures raw Telegram messages
- `itc_normalize.py`: Converts to canonical format
- `itc_route.py`: Routes messages to appropriate destinations

### Market Data
- `market_stream.py`: Captures exchange data (OHLCV)
- Stores in `.openclaw/market/candles_1m.jsonl`

### Trading Simulation
- `sim_runner.py`: Runs two different strategies:
  - `SIM_A`: Pure market-structure (price regime) long/flat
  - `SIM_B`: Market-structure + ITC sentiment signals
- Each sim starts with $1000 capital

### Governance
- Daily loss limit: 3%
- Max drawdown kill: 15%
- Max trades per day: 30

### Reporting
- `daily_rollup.py`: Generates daily performance metrics
- Ledger stored in `.openclaw/economics/economics.log`

## File Structure

```
.openclaw/
├── itc/
│   ├── raw/               # Raw Telegram data
│   └── canon/             # Canonical format
├── market/                # Market data (candles, funding)
├── sim/
│   ├── SIM_A/             # Strategy A files
│   └── SIM_B/             # Strategy B files
├── economics/             # Performance ledger
├── secrets/               # API keys, session data
├── pipelines/             # Configuration files
└── scripts/               # Pipeline scripts
```

## Usage

1. Configure your Telegram API credentials in `.openclaw/secrets/`
2. Start the ingestion: `python scripts/telethon_ingest.py`
3. Start market data collection: `python scripts/market_stream.py`
4. Run simulations: `python scripts/sim_runner.py`
5. Generate reports: `python scripts/daily_rollup.py`

## Governance Constraints

The system enforces strict governance rules:
- No parameter changes during the month-long evaluation period
- Automatic halting when drawdown or daily loss limits are reached
- Trade frequency limits to prevent overtrading

These constraints ensure a fair evaluation of the trading strategies.