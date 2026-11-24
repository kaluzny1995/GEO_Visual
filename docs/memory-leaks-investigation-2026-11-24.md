# Memory leaks investigation 2026-11-24

## Memory leaks investigation 2026-11-24

### Symptom

Host memory was **33 % before the 2026-11-24 pipeline run and 35.2 % after it**
(+~1.4 GiB on a 62.5 GiB host). This follow-up checks the Streamlit dashboard
after yesterday's engine-close and cache-bound changes.

### Finding

No Streamlit leak. The dashboard container held **103.4 MiB / 1 GiB** after the
run, lower than the previous day's measurement. The query cache is still bounded
by `cache_ttl_seconds=300` / `cache_max_entries=32`, and the provider is created
once per process.

The host increase is the desktop session:

| Measurement | Value |
|-------------|------:|
| `gnome-system-monitor` | 10.65 GiB, +0.87 GiB since 23 Nov |
| Chrome | 6.54 GiB, +0.21 GiB since 23 Nov |
| All nine GEO containers | 1.95 GiB |
| GEO_Visual container | 103.4 MiB |

`gnome-system-monitor` is the same process identified on 2026-11-23 and is still
growing ~1.1 GiB/day.

### Code status

No new leak and no code change today. The 2026-11-23 fix is deployed:
`clear_connection_cache()` closes the cached provider's SQLAlchemy engine before
clearing Streamlit's caches, so repeated "Recheck connection" clicks cannot
orphan connection pools. The AppTest rerun check remains flat (welcome page
~180 MiB, map page ~228 MiB).

### Verification

```bash
cd GEO_Visual
conda run -n geo_visual_311 python -m pytest -q
docker stats --no-stream geo_e2e-geo_streamlit-1
```

### Conclusion

GEO_Visual does not explain the host increase. Closing or restarting
`gnome-system-monitor` releases its ~10.6 GiB history buffer. After the monitor exited at ~18:44, host used fell from 22.0 GiB (35.2 %) to 11.1 GiB (17.6 %), confirming the attribution. Full evidence is
in [GEO_E2E — Memory leaks investigation 2026-11-24](../../GEO_E2E/docs/memory-leaks-investigation-2026-11-24.md).
