# M5: ONNX Runtime memory arena

Date: 2026-10-15. Machine: i5-8365U, 4 intra-op threads for each voice. onnxruntime 1.30.0.
Script: `scripts/measure_m5_arena.py` (one process for each variant). Results: `bench/results/m5/`, logs: `bench/results/logs/m5/`.

## 1. Method

- The 6 default voices (`DEFAULT_VOICES`), loaded as the daemon loads them (`load_voices`, aligned models).
- RSS (VmRSS) after load, after one long text for each voice (L1 for the Polish voices, an English text of 1000 characters for the English voices), and after rounds of all corpus texts (`bench/corpus.json`) or 2 English texts.
- RTF: synthesis time divided by audio time, median of 5 runs (series 1) and 15 runs (series 2), for `zenski` and `en_hfc_female`, short and long text. No playback.

Variants:

| Variant | Setting |
|---|---|
| arena | CPU memory arena on (the setting before this change) |
| no-arena | `SessionOptions.enable_cpu_mem_arena = False` |
| shrink | arena on, `RunOptions` entry `memory.enable_memory_arena_shrinkage = cpu:0` for each run |
| no-arena-no-pattern | no-arena, and `enable_mem_pattern = False` |

## 2. Measured facts

RSS in MB, series 1 (3 rounds):

| Variant | After load | After one long text for each voice | End | Peak |
|---|---:|---:|---:|---:|
| arena | 627 | 1723 | 2010 | 2010 |
| no-arena | 524 | 572 | 586 | 808 |
| shrink | 558 | 609 | 615 | 1009 |
| no-arena-no-pattern | 536 | 563 | 579 | 784 |

Series 2 (1 round, 15 RTF runs), RSS at the end: arena 2222, shrink 855 (peak 1155), no-arena 592 (peak 813).

Median RTF (`zenski` short / long, `en_hfc_female` short / long):

| Variant | Series 1 | Series 2 |
|---|---|---|
| arena | 0.076 / 0.077 / 0.077 / 0.076 | 0.088 / 0.086 / 0.083 / 0.084 |
| no-arena | 0.083 / 0.092 / 0.088 / 0.091 | 0.083 / 0.091 / 0.082 / 0.079 |
| shrink | 0.081 / 0.084 / 0.079 / 0.080 | 0.090 / 0.090 / 0.091 / 0.094 |
| no-arena-no-pattern | 0.083 / 0.084 / 0.086 / 0.082 | not measured |

Live check of the daemon with no-arena: RSS 521 MB after load, 574 MB after one sentence with each of the 6 voices. All 6 voices spoke.

Live daemon with one voice (`--voice zenski=pl_PL-zenski_wg_glos-medium`), no-arena:

| Point | RSS | Peak (VmHWM) |
|---|---:|---:|
| After load | 151 MB | 158 MB |
| After a short sentence (S1) | 166 MB | 182 MB |
| After 20 s of L1, then cancel | 214 MB | 412 MB |

## 3. Observations

1. With the arena, RSS increases with each new longest input of a voice. The earlier value of 1509 MB (`docs/voices.md`) was after one synthesis for each voice. After all corpus texts, RSS was 2010 and 2222 MB. This is above the target of 1.5 GB.
2. Without the arena, RSS stays near the RSS after load (+50 to +70 MB).
3. The RTF of the same variant changed by up to 17 % between the two series (arena: +8 to +17 %). The differences between the variants are in this range. No variant is clearly slower.
4. `enable_mem_pattern = False` gives no additional decrease.
5. shrink gives a higher and less stable RSS than no-arena (615 and 855 MB at the end).

## 4. Limits

1 machine, 2 series. RTF was measured without playback and without other load. TTFA was not measured again.

## 5. Decision

No-arena: `PiperBackend` sets `enable_cpu_mem_arena = False` (test: `tests/test_piper_memory.py`). Reason: the lowest and most stable RSS, one setting, and no RTF change that is larger than the noise of the measurement. With 6 voices, RSS is approximately 0.6 GB, so there is space for more voices below 1.5 GB.
