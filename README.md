# solana-token-flags

A daily, machine-readable list of tokens traded in the top Meteora DLMM pools that carry **Token-2022 transfer taxes or issuer controls**: transfer fee, permanent delegate (issuer can pull tokens from any wallet), pausable mint, transfer hook, plus whether mint and freeze authority are still live.

Why: a 3% transfer tax is paid on every deposit, withdrawal, swap and fee claim. For a liquidity provider that is more than a day of fees per round trip. Aggregator quotes and pool leaderboards do not show it. On 2026-09-08, 10 of the 39 hottest DLMM pools were tax tokens.

## Files

1. `data/latest.md` — human table, flagged tokens only, sorted by 24h pool volume.
2. `data/latest.json` — every mint seen in the scanned pools with all fields, flagged or not.
3. `data/history/YYYY-MM-DD.json` — flagged set per day, for tracking new listings.

Raw URL for bots: `https://raw.githubusercontent.com/Sirovensky/solana-token-flags/main/data/latest.json`

## Fields

`program` (spl-token | token-2022), `transfer_fee_bps`, `permanent_delegate`, `pausable`, `transfer_hook`, `mint_authority`, `freeze_authority`, `decimals`, `symbol`, `holders`, `pools` (DLMM pool addresses), `pool_volume_24h` (USD, summed over the token's scanned pools).

## How it runs

GitHub Actions, daily at 06:17 UTC (`.github/workflows/daily.yml`). `scan.py` needs only `requests`; run it locally with `SOLANA_RPC=<your rpc> python3 scan.py`. Scans up to 600 pools with TVL ≥ $20k ordered by 24h volume, reads every mint with `getMultipleAccounts`.

Related tools: [dlmm-screen](https://github.com/Sirovensky/dlmm-screen) (interactive pool screener with the same flags) and [Cookie Cleaner](https://github.com/Sirovensky/cookie-cleaner).

MIT.
