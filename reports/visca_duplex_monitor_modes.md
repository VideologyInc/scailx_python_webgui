# VISCA Duplex Monitor — Test Methodology and Results

Date: 2026-08-07
Tool: `tests/visca_duplex_monitor.py` (diagnostic script, not collected by pytest)
Device: `/dev/links/lvds2mipi_1`, 9600 baud 8N1
Camera: Videology zoomblock, `camera_info` = `905000200466010003ff`
Driver: `vdlg_lvds.serial.LvdsSerial`

This document describes how each of the six modes conducts its test and what it
measured on a live camera. It complements `visca_lvds_duplex_report.md`, which
covers the pass/fail pytest checks in `tests/test_lvds_duplex.py`.

---

## 1. Shared harness

### VISCA reply decoding

Every reply is split on `FF` terminators into individual messages, each
classified from the second byte:

| Pattern | Kind | Meaning |
|---|---|---|
| `90 4z FF` | ACK | Command accepted, executing in socket *z* |
| `90 5z FF` | Completion | The command in socket *z* has finished |
| `90 50 <data> FF` | Data | Inquiry reply (socket 0 — inquiries use no socket) |
| `90 6z <err> FF` | Error | `02` syntax, `03` buffer full, `04` cancelled, `41` not executable |

### What "CONTAMINATED" means

A reply is flagged contaminated when it contains bytes that do not belong to the
transaction that read it. The rule is structural, not length-based:

- An **inquiry** must return exactly one data message and nothing else.
- A **command** must return an ACK, optionally followed by the Completion **for
  that same socket**. A Completion for a *different* socket is by definition
  left over from an earlier command.

Contamination is not a delivery failure. The command was received and accepted —
the ACK proves it. What is wrong is the framing of the reply. A separate
`timeouts` counter tracks genuine non-delivery, and `wait_and_recv()` returning
`False` is handled explicitly.

### Two ways the modes drive the link

| | `transceive()` modes | Raw modes |
|---|---|---|
| Modes | `seq`, `duplex`, `zoom`, `probe` | `sockets`, `cancel` |
| Method | `LvdsSerial.transceive()` | `send()` + manual `get_rx_count()`/`recv()` polling |
| RX flush | Yes — before every send | Never |
| Purpose | Measure the driver as applications actually use it | Observe raw camera behaviour the driver hides |

The raw modes exist because `transceive()` flushes the RX FIFO before every
send, which destroys exactly the delayed Completions worth watching.

### Anatomy of one `transceive()` call

Measured round trip for a `zoom_pos` inquiry is ~26.5 ms, which decomposes as:

| Component | Time | Source |
|---|---|---|
| Wire time (5 bytes out, 7 bytes back) | 12.5 ms | 9600 baud, 1.042 ms/byte |
| Trailing quiet window | 10.0 ms | `stop_wait_ms` default in `LvdsSerial.__init__` |
| ioctl + polling overhead | ~4 ms | repeated `open()`/`ioctl()` per poll |

Over half of each transaction is **not** wire time. The 10 ms quiet window is the
arbitrary cutoff that decides whether a Completion is judged part of this reply
or left dangling for a later one.

---

## 2. Mode `seq` — uncontended baseline

**Purpose.** Establish the best achievable rate when nothing competes for the link.

**Method.** A single thread calls `transceive()` with `zoom_pos` (`81090447FF`)
back to back for the configured duration. One channel, one thread, no commands,
nothing moving. Every reply is decoded and checked against the inquiry rule.

**Command used.** `81090447FF` — read-only, changes no camera state.

**Run.** `visca_duplex_monitor.py seq -t 3`

### Result

```
read       113 clean,    0 contaminated,   0 timeouts  =>  37.37 Hz   clean
Combined clean throughput: 37.37 Hz over 3.02s
```

| Metric | Value |
|---|---|
| Rate | **37.37 Hz** (26.8 ms per round trip) |
| Contaminated | 0 |
| Timeouts | 0 |

**Interpretation.** A single uncontended VISCA exchange comfortably exceeds the
30 Hz target. Any shortfall in the other modes is therefore caused by contention
or protocol handling, not by the link being inherently too slow for 30 Hz.

---

## 3. Mode `duplex` — two read-only channels concurrently

**Purpose.** Determine whether two independent streams can each sustain 30 Hz,
using traffic that cannot possibly interfere at the protocol level.

**Method.** Two threads share one `LvdsSerial` instance. Thread A loops
`zoom_pos`, thread B loops `camera_info`. Both are inquiries, so no socket is
consumed, no motor moves, and no Completion is ever generated — any interference
observed must come from the transport itself. The two commands have different
reply lengths (7 vs 10 bytes), so cross-talk between channels would be visible.
With `--uart`, a third thread concurrently samples the FPGA `busy_tx`/`busy_rx`
status bits.

**Commands used.** `81090447FF` (zoom_pos), `81090002FF` (camera_info).

**Run.** `visca_duplex_monitor.py duplex -t 3 --uart`

### Result

```
A/read      52 clean,    0 contaminated,   0 timeouts  =>  17.26 Hz   clean
B/read      52 clean,    0 contaminated,   0 timeouts  =>  17.09 Hz   clean

Combined clean throughput: 34.16 Hz over 3.04s
Per-channel target for full duplex: 30 Hz each
  A/read    17.26 Hz  below target
  B/read    17.09 Hz  below target

UART status sampled 3923 times; busy_tx and busy_rx asserted simultaneously: 0 times
```

| Metric | Value |
|---|---|
| Channel A | 17.26 Hz, 0 contaminated |
| Channel B | 17.09 Hz, 0 contaminated |
| Combined | 34.16 Hz (vs 37.37 Hz for one channel alone) |
| Simultaneous busy_tx + busy_rx | **0 of 3923 samples** |
| Per-transaction latency | ~57-59 ms, roughly double the solo figure |

**Interpretation.** Two conclusions, from independent evidence.

Adding a second channel did not increase total throughput — it *divided* a fixed
pipe, and per-transaction latency doubled from ~27 ms to ~58 ms. Each channel
now waits its turn. That is the signature of serialization, not parallelism.

Separately, the hardware never once had both directions active simultaneously
across 3923 samples. The link is physically half-duplex, independent of how the
driver is written.

Note that with pure inquiry traffic the result is perfectly **clean** — zero
contamination. Contamination is therefore not caused by concurrency alone.

---

## 4. Mode `zoom` — command writes + status reads concurrently

**Purpose.** Reproduce the actual field pattern that produced the ~7 Hz ceiling:
an operator adjusting zoom while the GUI polls position.

**Method.** Two threads share the connection. The writer loops `zoom_direct`
alternating between zoom-table scales 1 and 10 (maximum lens travel, so
Completion latency is maximised). The reader loops `zoom_pos`. Unlike `duplex`,
the writer issues real commands that occupy a socket and take physical time to
finish, so delayed Completions are in play.

**Commands used.** `8101044700000000FF` / `8101044704000000FF` (zoom_direct),
`81090447FF` (zoom_pos).

**Run.** `visca_duplex_monitor.py zoom -t 3`

### Result

```
W/zoom      25 clean,   27 contaminated,   0 timeouts  =>   8.22 Hz   52% bad
R/read      37 clean,   14 contaminated,   0 timeouts  =>  12.28 Hz   27% bad

Combined clean throughput: 20.39 Hz over 3.04s
```

| Channel | Carried (all transactions) | Usable (clean replies) | Contaminated | Timeouts |
|---|---|---|---|---|
| Writer (zoom_direct) | **17.10 Hz** (52) | 8.22 Hz (25) | 27 (52%) | 0 |
| Reader (zoom_pos) | **16.93 Hz** (51) | 12.28 Hz (37) | 14 (27%) | 0 |

Representative contaminated write:

```
zoom_direct s10  8101044704000000FF -> 9042ff9051ff   ACK sock2 + Completion sock1
```

**Interpretation.** The distinction between *carried* and *usable* rate matters
here, and is easy to misread.

Contamination is **not** a throughput failure. The link carried ~34 transactions
per second in total — the same as `duplex` mode's 34.16 Hz — and **timeouts
remained 0**, so nothing was lost on the wire. Every command was sent, received
and answered. Over half the writer's replies simply came back mis-framed. The
contamination spoiled capacity that had already been spent; it did not reduce
the capacity itself.

| Mode | Carried | Usable |
|---|---|---|
| `duplex` (inquiries only) | 34.16 Hz | 34.16 Hz |
| `zoom` (writes + reads) | ~34.0 Hz | 20.39 Hz |

So the two defects are independent and need separate fixes. Eliminating
contamination entirely would still leave ~17 Hz per channel, short of the 30 Hz
target, because that ceiling comes from half-duplex sharing (proven by `duplex`,
which is perfectly clean at the same rate). Conversely, unlimited bandwidth would
not prevent contamination, because `probe` produces it with the link nearly idle.

The 52% figure for writes is higher than the pytest run reported because this
mode defaults to scales 1↔10 (maximum travel, maximum Completion delay). Using
`--scales 1 2` reproduces the gentler pattern.

---

## 5. Mode `probe` — sequential, single-threaded

**Purpose.** Determine whether contamination requires concurrency at all.

**Method.** Strictly one thread, one transaction at a time. Read `zoom_pos` once
to establish the idle baseline, then repeat: send one `zoom_direct`, then three
`zoom_pos` reads. Nothing overlaps; each call returns before the next begins. Any
contamination observed here cannot be attributed to threading.

**Run.** `visca_duplex_monitor.py probe --cycles 4`

### Result

```
write        3 clean,    1 contaminated,   0 timeouts  =>   6.41 Hz   25% bad
read        10 clean,    3 contaminated,   0 timeouts  =>  21.37 Hz   23% bad
```

Transaction log excerpts:

```
[0.027] write  zoom_direct s1  -> 9042ff                ACK sock2
[0.054] read   zoom_pos        -> 9051ff9050000a0f0dff  Completion sock1 + data   ** CONTAMINATED
[0.134] write  zoom_direct s10 -> 9041ff9052ff          ACK sock1 + Completion sock2  ** CONTAMINATED
[0.277] read   zoom_pos        -> 9050000c0106ff9051ff  data + Completion sock1   ** CONTAMINATED
[0.387] read   zoom_pos        -> 9052ff9050000c0106ff  Completion sock2 + data   ** CONTAMINATED
```

**Interpretation.** Contamination occurs with **zero concurrency**. This is the
single most important result in this document: the defect is not a threading
problem, it is that `transceive()` keeps no record of outstanding Completions.
A stale Completion can surface on any later transaction, single-threaded or not.

Critically, the stray bytes appear **both before and after** the real payload.
The `9051ff9050000a0f0dff` and `9052ff9050000c0106ff` cases put junk *first* —
any parser that assumes the reply begins at byte 0 reads `9051ff` as its answer
and extracts a nonsense zoom position. That is a silently wrong value, not a
visible error.

---

## 6. Mode `sockets` — socket allocation and buffer exhaustion

**Purpose.** Observe how the camera allocates command sockets, what happens when
they are all occupied, and how quickly they drain.

**Method.** Bypasses `transceive()` entirely. Fires `--burst` `zoom_direct`
commands back to back using `send()`, **without** waiting for Completions, so
sockets accumulate. Between sends it listens for `--gap` milliseconds, polling
`get_rx_count()`/`recv()` and timestamping every message. After the burst it
stops sending and listens passively for `--drain` seconds. Each ACK is then
paired with the Completion that later released its socket.

**Run A.** `visca_duplex_monitor.py sockets --burst 8 --gap 30 --drain 2`

### Result A — correctly paced pipelining

```
[  0.000] TX   8101044700000000FF   zoom_direct s1
[  0.015] RX   9042ff               ACK sock2
[  0.018] RX   9051ff               Completion sock1
[  0.032] TX   8101044704000000FF   zoom_direct s10
[  0.049] RX   9041ff               ACK sock1
[  0.051] RX   9052ff               Completion sock2
...
[  0.226] TX   8101044704000000FF   zoom_direct s10
[  0.241] RX   9041ff               ACK sock1
[  0.251] RX   9052ff               Completion sock2

ACKs received      : 8  (sockets used: 1, 2)
Completions        : 8
Errors / other     : 0
```

Socket hold times: 35.9, 35.2, 38.3, 39.5, 40.7, 40.6, 42.7 ms.

| Metric | Value |
|---|---|
| Commands accepted | **8 of 8** |
| Completions | 8 of 8 |
| Errors | 0 |
| Elapsed | 251 ms → **~32 commands/sec**, fully ACKed and completed |

In a separate run with longer lens travel (hold times ~65-70 ms) the camera
rotated through **three** sockets — `ACK sock1`, `ACK sock2`, `ACK sock3` — before
reusing socket 1. Standard VISCA specifies two command buffers; this camera
provides at least three. A third socket appears whenever Completion latency
exceeds the send spacing enough for three commands to be outstanding at once.
When all sockets are occupied the camera replies `906003ff` (command buffer
full), which is a clean rejection, not a silent drop.

**Run B.** `visca_duplex_monitor.py sockets --burst 6 --gap 5 --drain 2`

### Result B — transmit overrun

```
[  0.000] TX   8101044700000000FF   zoom_direct s1
[  0.007] TX   8101044704000000FF   zoom_direct s10
[  0.014] TX   8101044700000000FF   zoom_direct s1
[  0.022] TX   8101044704000000FF   zoom_direct s10
[  0.029] TX   8101044700000000FF   zoom_direct s1
[  0.036] TX   8101044704000000FF   zoom_direct s10

--- burst done, listening for 2.0s with nothing being sent ---
[  0.053] RX   906002ff             ERROR sock0 (syntax error)

ACKs received      : 0  (sockets used: none)
Completions        : 0
Errors / other     : 1
```

Six commands produced **zero** ACKs and a single syntax error. This is the
"some actions get no response" behaviour noted in commit 750bed7.

### Pacing sweep

Six commands per run, varying the inter-send gap. Two independent sweeps:

| Gap | Sweep 1 ACKs | Sweep 2 ACKs | Sockets seen |
|---|---|---|---|
| 5 ms | 0/6 | 0/6 | none |
| 10 ms | 1/6 | 0/6 | none |
| 15 ms | 4/6 | 3/6 | 1, 2, 3 |
| 20 ms | 5/6 | 6/6 | 1, 2, 3 |
| 25 ms | 6/6 | 6/6 | 1, 2, 3 |
| 30 ms | 6/6 | 6/6 | 1, 2 |
| 40 ms | 6/6 | 5/6 | 1, 2 |

**Interpretation.** Below ~15 ms spacing the link fails catastrophically and
silently. Above ~20 ms it is reliable, though the transition is not perfectly
sharp — the odd single-frame loss still appears at 40 ms, so this is a
probability gradient rather than a hard threshold.

The cause is transmit pacing arithmetic. At 9600 baud 8N1 each byte takes
1.042 ms, so a 9-byte `zoom_direct` occupies the wire for **9.4 ms**. Sending
every 5 ms attempts to push ~56 ms of traffic through a 36 ms window.
`LvdsSerial.send()` performs no `busy_tx` check before writing — it loads the
ioctl buffer and fires — so a send issued while a previous frame is still
shifting out corrupts it. Corrupted frames observed in this regime
(`549041ff`, `fa9042ff`, `90609041ff`) show exactly this: valid messages with
stray bytes attached or bytes missing mid-frame.

`transceive()` masks this problem by accident, since blocking for a reply
enforces ~26 ms spacing. Any code calling `send()` directly, or two threads
sending concurrently, has no such protection.

---

## 7. Mode `cancel` — releasing a socket early

**Purpose.** Confirm that an in-flight command can be abandoned and its socket
reclaimed without waiting for the lens to finish moving.

**Method.** Send one `zoom_direct`, poll RX until the ACK reveals which socket
was assigned, then immediately send VISCA Cancel (`81 2z FF`) for that socket
while the lens is still travelling. Listen for the response.

**Run.** `visca_duplex_monitor.py cancel --drain 2`

### Result

```
[  0.000] TX   8101044700000000FF   zoom_direct s1
[  0.015] RX   9041ff               ACK sock1
[  0.018] TX   8121FF               cancel socket 1
[  0.028] RX   906104ff             ERROR sock1 (command cancelled)

socket 1: ACK -> 906104ff after 12.5 ms
Completions: 0
```

**Interpretation.** Cancel works exactly as specified. The socket was released
after 12.5 ms and answered `90 61 04 FF` (command cancelled) *instead of* a
Completion — note the Completion count is 0, so cancelling replaces the
Completion rather than adding to it. This is a usable escape hatch for
superseded zoom commands: rather than letting an obsolete movement run to
completion and emit a Completion nobody wants, cancel it and free the socket.

---

## 8. Cross-cutting findings

### Summary of all modes

| Mode | Carried | Usable | Contaminated | Key observation |
|---|---|---|---|---|
| `seq` | 37.37 Hz | 37.37 Hz | 0 | One channel alone beats 30 Hz easily |
| `duplex` | 34.16 Hz | 34.16 Hz | 0 | Fixed pipe divided, never both directions at once |
| `zoom` | ~34.0 Hz | 20.39 Hz | 41 | Same throughput as `duplex`, but 40% spoiled |
| `probe` | n/a | n/a | 4 | Corruption occurs with **no threads at all** |
| `sockets` | ~32 cmd/sec | ~32 cmd/sec | n/a | Pipelining across sockets works perfectly |
| `cancel` | n/a | n/a | n/a | Socket released in 12.5 ms |

Carried throughput is essentially constant at ~34 Hz across every concurrent
mode. What changes is how much of it is usable.

### Three distinct defects, previously conflated

1. **No Completion tracking.** `transceive()` returns after a 10 ms quiet window
   and keeps no record of outstanding Completions, so a late one surfaces on an
   unrelated transaction. Demonstrated single-threaded in `probe`.
2. **No socket pipelining.** The driver uses one socket at a time and blocks for
   a reply, achieving ~8 Hz of writes where the camera sustains ~32/sec across
   its sockets.
3. **No transmit pacing.** `send()` never checks `busy_tx`, so back-to-back sends
   below ~15 ms apart silently destroy each other.

Only the second is inherent to the transport. The first and third are driver
bugs, fixable without touching the hardware.

### Wire-time budget at 9600 baud

At 1.042 ms per byte:

| Exchange | Bytes | Wire time |
|---|---|---|
| `zoom_direct` + ACK + Completion | 9 out, 6 back | 15.6 ms |
| `zoom_pos` + reply | 5 out, 7 back | 12.5 ms |
| `camera_info` + reply | 5 out, 10 back | 15.6 ms |

Sustaining 30 Hz of commands **and** 30 Hz of status reads requires
30 × (15.6 + 12.5) = **843 ms of wire time per second — 84% utilisation** on a
link that can only move one direction at a time, before any software overhead.
Measured overhead is ~14 ms per transaction (10 ms quiet window plus ~4 ms of
ioctl polling), which pushes the real requirement far past 100%.

At 19200 baud the wire budget drops to 42%, which leaves workable headroom.

---

## 9. Conclusions

**30 Hz simultaneous command + status is not achievable at 9600 baud.** The wire
budget alone reaches 84% utilisation on a physically half-duplex link, confirmed
by 3923 UART samples that never showed both directions active at once.

**However, substantial improvement is available without any hardware change:**

- **Track ACK/Completion state per socket.** This eliminates contamination
  entirely — including the silently-wrong-value case where a stray Completion
  arrives *before* the real payload — and it fixes a defect that is present in
  ordinary single-threaded use, not only under concurrency.
- **Pipeline across the camera's sockets.** Measured ~32 commands/sec fully
  ACKed and completed, versus ~8 Hz today. Roughly a 4× improvement.
- **Pace transmissions.** Check `busy_tx` before sending, or enforce a minimum
  ~20 ms spacing, to close the silent-loss failure mode.
- **Reconsider the 10 ms `stop_wait_ms` quiet window.** It is over a third of
  each transaction's latency and is the arbitrary cutoff that decides whether a
  Completion is captured or orphaned.
- **Use VISCA Cancel for superseded commands** rather than letting obsolete zoom
  movements run to completion.

**For genuine 30 Hz duplex, raise the baud rate.** 19200 brings wire utilisation
to a workable 42%; the driver fixes above are still required to make the
resulting bandwidth usable.
