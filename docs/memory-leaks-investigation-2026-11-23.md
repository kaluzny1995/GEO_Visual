# Memory leaks investigation 2026-11-23

## Memory leaks investigation 2026-11-23

### Symptom

The stack had been up since 2026-11-17 without an error, while host memory grew
from **11.92 GiB to 19.63 GiB** (~**1.3 GiB/day**); the reported full-run span
was 8.7 → 22.2 GiB.

### Root cause

The host growth came from the desktop session, not the pipeline:
`gnome-system-monitor` held **9.74 GiB RSS** and grew ~**1.1 GiB/day**, Chrome
held ~6.3 GiB, and all nine GEO containers together held only ~2.6–3.4 GiB.
The Streamlit container itself stayed at ~0.24–0.35 GiB for the whole run.

### GEO_Visual audit

* `cached_query` is bounded: `st.cache_data(ttl=300, max_entries=32)` from
  `config.json`. The largest result (the 250,000-row distribution query) is
  capped by `read_dataframe`, so the cache cannot grow with the number of dates
  or page visits.
* `get_provider` is a single `st.cache_resource` engine; every query uses one
  short-lived SQLAlchemy transaction and returns a DataFrame.
* Plotly figures are rebuilt per rerun and are not stored in `st.session_state`;
  the Python `Figure` objects become garbage at the next rerun.
* A 5-rerun `AppTest` loop kept RSS flat: app page 179.7 → 179.9 MiB, US map
  page 227.9 → 227.6 MiB. No per-rerun leak.
* Streamlit itself is not given a memory limit in its process; Compose caps the
  container at 1 GiB.

One leak remained in the cache-clear path: `clear_connection_cache()` called
`get_provider.clear()` **without closing the provider**. Every "Recheck
connection" click therefore orphaned an engine with up to `pool_size +
max_overflow` connections and its buffers until the process exited. That is a
real leak for a long-lived dashboard server, even if users click the button
rarely.

### Change made

`utils/database.py` keeps a module-level reference to the cached provider:

```python
_PROVIDER: SupabasePostgresProvider | None = None
```

`clear_connection_cache()` now calls `_PROVIDER.close()` (which disposes the
SQLAlchemy pool) before clearing the Streamlit caches, then resets the
reference. A failed dispose is logged and does not block the recheck.

Tests in `test/test_database.py` assert that the old provider is closed exactly
once, that the reference is reset, and that clearing before the first query is
a no-op (never constructs a provider just to close it).

### Verification

```bash
cd GEO_Visual
conda run -n geo_visual_311 python -m pytest -q
```

To reproduce the rerun check, run `AppTest.from_file(...)` in a loop and read
`/proc/self/status` `VmRSS` between runs; the value stays flat at ~180 MiB for
the welcome page and ~228 MiB for the map page.

### Conclusion

GEO_Visual's query cache and rerun behaviour are bounded; the container stayed
small for the full run. The engine-close fix removes a connection-pool leak in
the cache-clear path and is now covered by tests. The 1.3 GiB/day host growth
was external (desktop system monitor / browser).
