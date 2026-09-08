#!/usr/bin/env python3
"""Daily scan: Token-2022 transfer taxes and issuer controls for every token traded in the
top Meteora DLMM pools. Writes data/latest.json, data/latest.md and data/history/<date>.json.

Only `requests` is needed. Uses the public Solana RPC (override with SOLANA_RPC).
"""
import datetime as dt, json, os, time, requests

API = "https://dlmm.datapi.meteora.ag/pools"
RPC = os.environ.get("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
T22 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def rpc(method, params):
    for attempt in range(5):
        r = requests.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=60)
        if r.status_code == 429:
            time.sleep(5 * (attempt + 1)); continue
        j = r.json()
        if "error" in j:
            raise RuntimeError(j["error"])
        return j["result"]
    raise RuntimeError("rpc rate limited")


def parse_mint(v):
    if not v or not v.get("data") or not isinstance(v["data"], dict):
        return None
    info = v["data"]["parsed"]["info"]
    ext = {e["extension"]: e.get("state", {}) for e in info.get("extensions", [])}
    fee = ext.get("transferFeeConfig", {}).get("newerTransferFee", {}).get("transferFeeBasisPoints", 0)
    return {
        "program": "token-2022" if v["owner"] == T22 else "spl-token",
        "transfer_fee_bps": fee,
        "permanent_delegate": "permanentDelegate" in ext,
        "pausable": "pausableConfig" in ext,
        "transfer_hook": bool(ext.get("transferHook", {}).get("programId")),
        "mint_authority": info.get("mintAuthority"),
        "freeze_authority": info.get("freezeAuthority"),
        "decimals": info.get("decimals"),
        "symbol": (ext.get("tokenMetadata") or {}).get("symbol"),
    }


def main():
    pools = []
    for page in (1, 2, 3):
        d = requests.get(API, params={"sort_by": "volume_24h:desc", "filter_by": "tvl>=20000", "page_size": 200, "page": page}, timeout=60).json()
        pools += d["data"]
        if page >= d.get("pages", 1):
            break
    mints = {}
    for p in pools:
        for side in ("token_x", "token_y"):
            t = p[side]; m = t["address"]
            e = mints.setdefault(m, {"symbol": t.get("symbol"), "name": t.get("name"), "holders": t.get("holders"), "pools": [], "pool_volume_24h": 0.0})
            e["pools"].append(p["address"]); e["pool_volume_24h"] += float(p["volume"]["24h"] or 0)
    # Whole-market coverage: Jupiter's top traded tokens (24h)
    try:
        top = requests.get("https://lite-api.jup.ag/tokens/v2/toptraded/24h", params={"limit": 200}, timeout=60).json()
        for t in top:
            st = t.get("stats24h") or {}
            e = mints.setdefault(t["id"], {"symbol": t.get("symbol"), "name": t.get("name"), "holders": t.get("holderCount"), "pools": [], "pool_volume_24h": 0.0})
            e["jup_volume_24h"] = float(st.get("buyVolume") or 0) + float(st.get("sellVolume") or 0)
            e["source"] = sorted(set((e.get("source") or []) + ["jupiter_top_traded"]))
    except Exception as ex:
        print("jupiter top traded failed:", ex)
    for m, e in mints.items():
        if e["pools"]:
            e["source"] = sorted(set((e.get("source") or []) + ["meteora_dlmm"]))
    addrs = list(mints)
    for i in range(0, len(addrs), 100):
        chunk = addrs[i:i + 100]
        res = rpc("getMultipleAccounts", [chunk, {"encoding": "jsonParsed"}])["value"]
        for m, v in zip(chunk, res):
            info = parse_mint(v) or {}
            mints[m].update(info)
            if info.get("symbol") and not mints[m].get("symbol"):
                mints[m]["symbol"] = info["symbol"]
        time.sleep(0.5)
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    flagged = {m: e for m, e in mints.items() if e.get("transfer_fee_bps") or e.get("permanent_delegate") or e.get("pausable") or e.get("transfer_hook")}
    out = {"generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "pools_scanned": len(pools), "mints_scanned": len(mints), "flagged_count": len(flagged), "mints": mints}
    os.makedirs(os.path.join(OUT, "history"), exist_ok=True)
    json.dump(out, open(os.path.join(OUT, "latest.json"), "w"), indent=0, sort_keys=True)
    json.dump({"generated_utc": out["generated_utc"], "flagged": flagged}, open(os.path.join(OUT, "history", today + ".json"), "w"), sort_keys=True)
    rows = sorted(flagged.items(), key=lambda kv: -(kv[1]["pool_volume_24h"] + kv[1].get("jup_volume_24h", 0)))
    with open(os.path.join(OUT, "latest.md"), "w") as f:
        f.write(f"# Flagged tokens — {today}\n\n{len(pools)} Meteora DLMM pools (TVL ≥ $20k) plus Jupiter's 200 top-traded tokens: {len(mints)} distinct mints, **{len(flagged)} flagged**.\n\n")
        f.write("| symbol | mint | transfer fee | permanent delegate | pausable | hook | mint auth | freeze auth | 24h volume (DLMM + Jupiter) | source |\n|---|---|---|---|---|---|---|---|---|---|\n")
        for m, e in rows:
            f.write(f"| {e.get('symbol') or ''} | `{m}` | {e.get('transfer_fee_bps', 0) / 100:.2f}% | {'yes' if e.get('permanent_delegate') else ''} | {'yes' if e.get('pausable') else ''} | {'yes' if e.get('transfer_hook') else ''} | {'live' if e.get('mint_authority') else ''} | {'live' if e.get('freeze_authority') else ''} | ${e['pool_volume_24h'] + e.get('jup_volume_24h', 0):,.0f} | {', '.join(e.get('source') or [])} |\n")
    print(f"pools {len(pools)} mints {len(mints)} flagged {len(flagged)}")


if __name__ == "__main__":
    main()
