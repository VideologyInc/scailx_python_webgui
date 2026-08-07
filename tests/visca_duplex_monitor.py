#! /usr/bin/env python3
"""

Interactive diagnostic for the LVDS VISCA serial link. Prints every
transaction (what was sent, what came back, how long it took) as it happens,
with each reply decoded into its individual VISCA messages, so the ACK /
Completion / inquiry-data traffic can be watched directly in the terminal.

This is a tool, not a pytest - the filename is deliberately not test_*.py so
pytest will not collect it. For the pass/fail version of the same questions,
see test_lvds_duplex.py.

Modes:
  seq     one channel alone, sequential. Baseline round-trip rate.
  duplex  2 read-only inquiry channels on separate threads, same connection.
  zoom    zoom_direct writes + zoom_pos reads concurrently (the field pattern).
  probe   sequential zoom write followed by several reads, no threads. Shows
          a delayed Completion landing on an unrelated later transaction.
  sockets fills both camera command buffers to show socket allocation and the
          'command buffer full' rejection. Bypasses transceive().
  cancel  takes a socket with a zoom, then cancels it mid-flight.

Examples:
  ./visca_duplex_monitor.py probe
  ./visca_duplex_monitor.py zoom --duration 5
  ./visca_duplex_monitor.py duplex --interval 0.033 --uart
  ./visca_duplex_monitor.py sockets --burst 6
  ./visca_duplex_monitor.py cancel

2026.0807.  Created.

By: mkkamarudin@videologyinc.com

"""

import argparse
import glob
import json
import sys
import threading
import time

from pathlib import Path

from vdlg_lvds.serial import LvdsSerial


# Default per-transaction response timeout, in ms.
TIMEOUT = 1000

# Rate we are trying to reach on each channel independently, in Hz.
TARGET_HZ = 30

ASSETS = Path(__file__).resolve().parent / "assets"


#######################################################################################
# Terminal helpers

class Colors:
    def __init__(self, enabled):
        self.reset = "\033[0m" if enabled else ""
        self.dim = "\033[2m" if enabled else ""
        self.red = "\033[31m" if enabled else ""
        self.green = "\033[32m" if enabled else ""
        self.yellow = "\033[33m" if enabled else ""
        self.blue = "\033[34m" if enabled else ""
        self.magenta = "\033[35m" if enabled else ""
        self.cyan = "\033[36m" if enabled else ""
        self.bold = "\033[1m" if enabled else ""


C = Colors(sys.stdout.isatty())

# Serialize prints so 2 threads cannot interleave mid-line.
print_lock = threading.Lock()


def emit(line):
    with print_lock:
        print(line, flush=True)


def banner(title):
    emit(f"\n{C.bold}{'=' * 78}{C.reset}")
    emit(f"{C.bold}{title}{C.reset}")
    emit(f"{C.bold}{'=' * 78}{C.reset}")


#######################################################################################
# VISCA reply decoding
#
# Every reply from the camera is one or more FF-terminated messages:
#   90 4z FF          ACK        - accepted, now executing in socket z
#   90 5z FF          Completion - the command in socket z has finished
#   90 50 <data> FF   Inquiry reply (socket 0 = no socket used), data payload
#   90 6z <err> FF    Error
# A single transceive() can return several of these concatenated, which is
# exactly the symptom this tool exists to make visible.

VISCA_ERRORS = {
    0x02: "syntax error",
    0x03: "command buffer full",
    0x04: "command cancelled",
    0x05: "no socket",
    0x41: "command not executable",
}


# Split a raw reply into individual FF-terminated VISCA messages. Any trailing
# bytes with no terminator are returned as a final fragment.
def split_messages(raw):
    messages = []
    current = bytearray()
    for byte in raw:
        current.append(byte)
        if byte == 0xFF:
            messages.append(bytes(current))
            current = bytearray()
    if current:
        messages.append(bytes(current))
    return messages


# Human-readable description of one VISCA message, plus whether it carries
# inquiry data (as opposed to being an ACK/Completion/error).
# Message kinds, as classified for the cleanliness check below.
ACK = "ack"
COMPLETION = "completion"
DATA = "data"
OTHER = "other"


def describe_message(msg):
    if len(msg) < 3 or msg[-1] != 0xFF:
        return f"malformed <{msg.hex()}>", OTHER, None

    kind = msg[1] >> 4
    socket = msg[1] & 0x0F

    if kind == 4:
        return f"ACK sock{socket}", ACK, socket

    if kind == 5:
        if len(msg) == 3:
            return f"Completion sock{socket}", COMPLETION, socket
        payload = msg[2:-1]
        # Inquiry payloads are commonly 4 nibbles forming a 16-bit value,
        # e.g. zoom position 0p 0q 0r 0s.
        if len(payload) == 4 and all(b <= 0x0F for b in payload):
            value = (payload[0] << 12) | (payload[1] << 8) | (payload[2] << 4) | payload[3]
            return f"data sock{socket} [{payload.hex()}] = 0x{value:04X} ({value})", DATA, socket
        return f"data sock{socket} [{payload.hex()}]", DATA, socket

    if kind == 6:
        code = msg[2] if len(msg) > 3 else None
        return (f"ERROR sock{socket} "
                f"({VISCA_ERRORS.get(code, f'code 0x{code:02X}' if code else 'unknown')})"), OTHER, socket

    return f"unknown <{msg.hex()}>", OTHER, socket


# Decode a whole reply into a printable summary plus the (kind, socket) of
# each message it contained.
def decode_reply(raw):
    parts = []
    classified = []
    for msg in split_messages(raw):
        text, kind, socket = describe_message(msg)
        parts.append(text)
        classified.append((kind, socket))
    return " + ".join(parts), classified


# Is this reply exactly what the channel asked for, and nothing else?
#
# An inquiry expects one data message, full stop. A command expects an ACK,
# optionally followed by the Completion for that same socket. A Completion
# for any *other* socket is a stale reply from an earlier command that the
# driver never collected - the defect this tool is looking for.
def reply_is_clean(classified, expect):
    if not classified:
        return False

    kinds = [kind for kind, _ in classified]

    if expect == "data":
        return kinds == [DATA]

    if kinds[0] != ACK:
        return False
    ack_socket = classified[0][1]
    for kind, socket in classified[1:]:
        if kind != COMPLETION or socket != ack_socket:
            return False
    return True


#######################################################################################
# Transaction logging

class Channel:
    """One logical request/response stream, with its own live log and stats."""

    def __init__(self, name, color, expect):
        self.name = name
        self.color = color
        # expect is "data" for inquiry channels, "control" for command channels.
        self.expect = expect
        self.ok = 0
        self.anomalies = 0
        self.timeouts = 0
        self.elapsed = 0.0
        self.records = []

    # Run one transaction and print it. Returns True if the reply looked clean.
    def transact(self, device, label, hex_command, t_zero, verbose=True):
        data = bytearray.fromhex(hex_command)
        t0 = time.monotonic()
        reply = device.transceive(data, start_wait_ms=TIMEOUT)
        t1 = time.monotonic()

        stamp = t0 - t_zero
        duration_ms = (t1 - t0) * 1000

        # wait_and_recv() returns False on timeout, not None or b"".
        if not reply:
            self.timeouts += 1
            note = f"{C.red}** NO RESPONSE (timeout){C.reset}"
            if verbose:
                emit(f"{C.dim}[{stamp:7.3f}]{C.reset} {self.color}{self.name:<7}{C.reset} "
                     f"{label:<14} {hex_command:<20} -> {'':<24} {note} {duration_ms:6.1f}ms")
            self.records.append((stamp, label, hex_command, None, duration_ms))
            return False

        reply_hex = reply.hex()
        summary, classified = decode_reply(reply)
        clean = reply_is_clean(classified, self.expect)

        if clean:
            self.ok += 1
            note = ""
        else:
            self.anomalies += 1
            note = f"{C.red}** CONTAMINATED{C.reset}"

        if verbose:
            emit(f"{C.dim}[{stamp:7.3f}]{C.reset} {self.color}{self.name:<7}{C.reset} "
                 f"{label:<14} {hex_command:<20} -> {reply_hex:<24} "
                 f"{C.cyan}{summary}{C.reset} {note} {C.dim}{duration_ms:6.1f}ms{C.reset}")

        self.records.append((stamp, label, hex_command, reply_hex, duration_ms))
        return clean

    def attempts(self):
        return self.ok + self.anomalies + self.timeouts

    # Transactions per second that completed with a usable reply.
    def rate_hz(self):
        return self.ok / self.elapsed if self.elapsed > 0 else 0.0

    # Transactions per second actually carried by the link, usable or not.
    # This is the throughput figure; rate_hz() is what survives it.
    def attempt_rate_hz(self):
        return self.attempts() / self.elapsed if self.elapsed > 0 else 0.0


# Loop one channel for duration_sec, optionally pacing requests.
def run_channel(channel, device, label, hex_command, duration_sec, t_zero, interval, verbose=True):
    start = time.monotonic()
    while time.monotonic() - start < duration_sec:
        channel.transact(device, label, hex_command, t_zero, verbose)
        if interval > 0:
            time.sleep(interval)
    channel.elapsed = time.monotonic() - start


#######################################################################################
# VISCA command assets

def load_visca():
    commands = json.loads((ASSETS / "visca_commands.json").read_text())
    zoom_table = json.loads((ASSETS / "visca_zoom_table.json").read_text())
    return commands["inquiry"], commands["commands"], zoom_table


# Build a zoom_direct write for a table scale of 1..10, same construction as
# test_lvds_zoom.py::visca_zoom_scale.
def zoom_write_hex(zoom_pqrs, zoom_table, scale):
    position = zoom_table[str(scale)]
    eight = "0" + position[0] + "0" + position[1] + "0" + position[2] + "0" + position[3]
    return zoom_pqrs[0:len("81010447")] + eight + "FF"


#######################################################################################
# UART busy-bit sampler
#
# The FPGA UART exposes busy_tx / busy_rx. If the link were truly full duplex,
# both would be asserted at once at some point while traffic is flowing.

class UartSampler(threading.Thread):
    def __init__(self, device):
        super().__init__(daemon=True)
        self.device = device
        self.stop_event = threading.Event()
        self.samples = 0
        self.both_busy = 0

    def run(self):
        while not self.stop_event.is_set():
            try:
                _, _, _, _, busy_rx, busy_tx = self.device.get_uart_status()
            except OSError:
                continue
            self.samples += 1
            if busy_rx and busy_tx:
                self.both_busy += 1

    def stop(self):
        self.stop_event.set()
        self.join(timeout=2.0)


#######################################################################################
# Modes

def mode_seq(device, args, inquiry, commands, zoom_table):
    banner("MODE: seq - one channel alone, sequential (baseline)")
    emit(f"{C.dim}Sending zoom_pos inquiries back to back for {args.duration:.1f}s. "
         f"Nothing else is touching the link.{C.reset}\n")

    channel = Channel("read", C.green, expect="data")
    t_zero = time.monotonic()
    run_channel(channel, device, "zoom_pos", inquiry["zoom_pos"], args.duration,
                t_zero, args.interval, verbose=not args.quiet)
    return [channel], time.monotonic() - t_zero


def mode_duplex(device, args, inquiry, commands, zoom_table):
    banner("MODE: duplex - 2 read-only channels concurrently")
    emit(f"{C.dim}2 threads share one LvdsSerial. Both send harmless inquiries, so nothing{C.reset}")
    emit(f"{C.dim}moves. Watch whether the 2 streams interleave or strictly alternate.{C.reset}\n")

    chan_a = Channel("A/read", C.green, expect="data")
    chan_b = Channel("B/read", C.magenta, expect="data")

    t_zero = time.monotonic()
    threads = [
        threading.Thread(target=run_channel, args=(
            chan_a, device, "zoom_pos", inquiry["zoom_pos"],
            args.duration, t_zero, args.interval, not args.quiet)),
        threading.Thread(target=run_channel, args=(
            chan_b, device, "camera_info", inquiry["camera_info"],
            args.duration, t_zero, args.interval, not args.quiet)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return [chan_a, chan_b], time.monotonic() - t_zero


def mode_zoom(device, args, inquiry, commands, zoom_table):
    banner("MODE: zoom - zoom writes + zoom_pos reads concurrently (field pattern)")
    emit(f"{C.dim}A writer thread drives zoom_direct between scales {args.scales}, while a{C.reset}")
    emit(f"{C.dim}reader thread polls zoom_pos. Zoom takes real time to move, so its{C.reset}")
    emit(f"{C.dim}Completion arrives late - watch for it landing on a read.{C.reset}\n")

    zoom_pqrs = commands["zoom_direct"]
    writer = Channel("W/zoom", C.yellow, expect="control")
    reader = Channel("R/read", C.green, expect="data")

    t_zero = time.monotonic()

    def write_loop():
        scales = args.scales
        i = 0
        start = time.monotonic()
        while time.monotonic() - start < args.duration:
            scale = scales[i % len(scales)]
            writer.transact(device, f"zoom_direct s{scale}",
                            zoom_write_hex(zoom_pqrs, zoom_table, scale),
                            t_zero, verbose=not args.quiet)
            i += 1
            if args.interval > 0:
                time.sleep(args.interval)
        writer.elapsed = time.monotonic() - start

    threads = [
        threading.Thread(target=write_loop),
        threading.Thread(target=run_channel, args=(
            reader, device, "zoom_pos", inquiry["zoom_pos"],
            args.duration, t_zero, args.interval, not args.quiet)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return [writer, reader], time.monotonic() - t_zero


def mode_probe(device, args, inquiry, commands, zoom_table):
    banner("MODE: probe - sequential only, no threads")
    emit(f"{C.dim}One zoom_direct, then {args.reads} zoom_pos reads, strictly one at a time.{C.reset}")
    emit(f"{C.dim}Any stray Completion appearing on a read here cannot be blamed on{C.reset}")
    emit(f"{C.dim}concurrency - there is none.{C.reset}\n")

    zoom_pqrs = commands["zoom_direct"]
    zoom_pos = inquiry["zoom_pos"]
    writer = Channel("write", C.yellow, expect="control")
    reader = Channel("read", C.green, expect="data")

    t_zero = time.monotonic()
    reader.transact(device, "zoom_pos idle", zoom_pos, t_zero)
    emit("")

    for cycle in range(args.cycles):
        scale = args.scales[cycle % len(args.scales)]
        emit(f"{C.dim}--- cycle {cycle + 1}: zoom to scale {scale}, then {args.reads} reads ---{C.reset}")
        writer.transact(device, f"zoom_direct s{scale}",
                        zoom_write_hex(zoom_pqrs, zoom_table, scale), t_zero)
        for _ in range(args.reads):
            reader.transact(device, "zoom_pos", zoom_pos, t_zero)
        emit("")

    elapsed = time.monotonic() - t_zero
    writer.elapsed = elapsed
    reader.elapsed = elapsed
    return [writer, reader], elapsed


#######################################################################################
# Raw socket experiments
#
# These bypass transceive() completely. transceive() flushes the RX FIFO before
# every send, which would throw away exactly the delayed Completions we want to
# watch. Instead we send() and then poll the RX count ourselves, timestamping
# every message the camera emits, so the full socket lifecycle is visible:
# allocate -> execute -> complete (or cancel).

class RxMonitor:
    """Passive RX reader. Never sends, never flushes; just timestamps replies."""

    def __init__(self, device, t_zero):
        self.device = device
        self.t_zero = t_zero
        self.buffer = bytearray()
        self.messages = []

    # Read whatever has arrived for duration_sec, printing each complete message.
    def pump(self, duration_sec, verbose=True):
        end = time.monotonic() + duration_sec
        while time.monotonic() < end:
            count = self.device.get_rx_count()
            if count:
                chunk = self.device.recv(count)
                stamp = time.monotonic() - self.t_zero
                self.buffer.extend(chunk)
                self._extract(stamp, verbose)
            else:
                time.sleep(0.0005)

    # Pull every complete FF-terminated message out of the buffer.
    def _extract(self, stamp, verbose):
        while True:
            end = self.buffer.find(0xFF)
            if end < 0:
                return
            msg = bytes(self.buffer[:end + 1])
            del self.buffer[:end + 1]
            text, kind, socket = describe_message(msg)
            self.messages.append((stamp, msg, kind, socket))
            if verbose:
                color = C.red if kind == OTHER else C.cyan
                emit(f"{C.dim}[{stamp:7.3f}]{C.reset} {C.green}RX{C.reset}   "
                     f"{msg.hex():<24} {color}{text}{C.reset}")


def raw_send(device, hex_command, label, t_zero, verbose=True):
    stamp = time.monotonic() - t_zero
    device.send(bytearray.fromhex(hex_command))
    if verbose:
        emit(f"{C.dim}[{stamp:7.3f}]{C.reset} {C.yellow}TX{C.reset}   "
             f"{hex_command:<24} {C.yellow}{label}{C.reset}")
    return stamp


# Pair each ACK with the Completion (or error) that later released its socket.
def report_socket_lifecycle(monitor):
    pending = {}
    emit(f"\n{C.bold}Socket lifecycle{C.reset}")
    for stamp, msg, kind, socket in monitor.messages:
        if kind == ACK:
            pending[socket] = stamp
        elif kind == COMPLETION and socket in pending:
            held = (stamp - pending.pop(socket)) * 1000
            emit(f"  socket {socket}: ACK -> Completion took {C.bold}{held:7.1f} ms{C.reset}")
        elif kind == OTHER and socket in pending:
            held = (stamp - pending.pop(socket)) * 1000
            emit(f"  socket {socket}: ACK -> {msg.hex()} after {held:7.1f} ms")
    for socket, stamp in pending.items():
        emit(f"  socket {socket}: {C.red}still occupied at end of run{C.reset} "
             f"(ACK at {stamp:.3f}s, no Completion seen)")
    if not monitor.messages:
        emit(f"  {C.red}nothing received{C.reset}")


def mode_sockets(device, args, inquiry, commands, zoom_table):
    banner("MODE: sockets - fill both command buffers and watch allocation")
    emit(f"{C.dim}Fires {args.burst} zoom_direct commands back to back WITHOUT waiting for{C.reset}")
    emit(f"{C.dim}their Completions, so sockets stay occupied. The camera has only 2{C.reset}")
    emit(f"{C.dim}command buffers - once both are busy it should answer 90 60 03 FF{C.reset}")
    emit(f"{C.dim}(command buffer full) instead of an ACK. Then we stop sending and just{C.reset}")
    emit(f"{C.dim}listen for {args.drain:.1f}s to watch the sockets drain.{C.reset}\n")

    zoom_pqrs = commands["zoom_direct"]
    device.recv()  # clear anything stale before we start counting

    t_zero = time.monotonic()
    monitor = RxMonitor(device, t_zero)

    for i in range(args.burst):
        scale = args.scales[i % len(args.scales)]
        raw_send(device, zoom_write_hex(zoom_pqrs, zoom_table, scale),
                 f"zoom_direct s{scale}", t_zero)
        # Short listen so each ACK is attributed to the command that caused it.
        monitor.pump(args.gap / 1000.0)

    emit(f"\n{C.dim}--- burst done, listening for {args.drain:.1f}s with nothing being sent ---{C.reset}")
    monitor.pump(args.drain)

    return monitor


def mode_cancel(device, args, inquiry, commands, zoom_table):
    banner("MODE: cancel - take a socket, then cancel it mid-flight")
    emit(f"{C.dim}Sends one zoom_direct, waits for its ACK to learn which socket it took,{C.reset}")
    emit(f"{C.dim}then sends VISCA Cancel (8x 2z FF) for that socket while the lens is{C.reset}")
    emit(f"{C.dim}still moving. A cancelled command answers 90 6z 04 FF instead of a{C.reset}")
    emit(f"{C.dim}Completion - which is how a socket gets released early.{C.reset}\n")

    zoom_pqrs = commands["zoom_direct"]
    device.recv()

    t_zero = time.monotonic()
    monitor = RxMonitor(device, t_zero)

    scale = args.scales[0]
    raw_send(device, zoom_write_hex(zoom_pqrs, zoom_table, scale), f"zoom_direct s{scale}", t_zero)

    # Listen until we know which socket the camera handed out.
    deadline = time.monotonic() + 1.0
    socket = None
    while socket is None and time.monotonic() < deadline:
        monitor.pump(0.005)
        for _, _, kind, sock in monitor.messages:
            if kind == ACK:
                socket = sock
                break

    if socket is None:
        emit(f"\n{C.red}No ACK received - cannot tell which socket to cancel.{C.reset}")
        return monitor

    emit(f"\n{C.dim}--- ACK came back on socket {socket}, cancelling it now ---{C.reset}")
    raw_send(device, f"812{socket}FF", f"cancel socket {socket}", t_zero)
    monitor.pump(args.drain)

    return monitor


MODES = {
    "seq": mode_seq,
    "duplex": mode_duplex,
    "zoom": mode_zoom,
    "probe": mode_probe,
    "sockets": mode_sockets,
    "cancel": mode_cancel,
}

# Modes that drive the link directly and report a socket timeline rather than
# per-channel throughput.
RAW_MODES = ("sockets", "cancel")


#######################################################################################
# Summary

def print_raw_summary(monitor, sampler):
    banner("SUMMARY")

    report_socket_lifecycle(monitor)

    sockets_used = sorted({s for _, _, kind, s in monitor.messages if kind == ACK})
    acks = sum(1 for _, _, kind, _ in monitor.messages if kind == ACK)
    completions = sum(1 for _, _, kind, _ in monitor.messages if kind == COMPLETION)
    errors = [(m, s) for _, m, kind, s in monitor.messages if kind == OTHER]

    emit(f"\n{C.bold}Totals{C.reset}")
    emit(f"  ACKs received      : {acks}  (sockets used: "
         f"{', '.join(str(s) for s in sockets_used) or 'none'})")
    emit(f"  Completions        : {completions}")
    emit(f"  Errors / other     : {len(errors)}")

    buffer_full = [m for m, _ in errors if len(m) > 3 and m[1] >> 4 == 6 and m[2] == 0x03]
    if buffer_full:
        emit(f"\n  {C.bold}{len(buffer_full)} x 'command buffer full' (90 60 03 FF){C.reset}")
        emit(f"  {C.dim}Both sockets were occupied, so the camera refused the command{C.reset}")
        emit(f"  {C.dim}outright. Those commands never executed - unlike a contaminated{C.reset}")
        emit(f"  {C.dim}reply, this is a genuine rejection.{C.reset}")

    cancelled = [m for m, _ in errors if len(m) > 3 and m[1] >> 4 == 6 and m[2] == 0x04]
    if cancelled:
        emit(f"\n  {C.bold}{len(cancelled)} x 'command cancelled' (90 6z 04 FF){C.reset}")
        emit(f"  {C.dim}The socket was released early instead of running to Completion.{C.reset}")

    if sampler:
        emit(f"\n  UART status sampled {sampler.samples} times; "
             f"busy_tx and busy_rx asserted simultaneously: "
             f"{C.bold}{sampler.both_busy}{C.reset} times")


def print_summary(channels, wall_clock, sampler, mode):
    banner("SUMMARY")

    emit(f"  {C.dim}'carried' = transactions the link actually completed; "
         f"'usable' = those with a clean reply.{C.reset}")
    emit(f"  {C.dim}The gap between them is wasted capacity, not lost speed.{C.reset}\n")

    total_ok = 0
    total_attempts = 0
    total_bad = 0
    for ch in channels:
        bad = ch.anomalies + ch.timeouts
        total_ok += ch.ok
        total_attempts += ch.attempts()
        total_bad += bad
        share = (100.0 * bad / ch.attempts()) if ch.attempts() else 0.0
        verdict = f"{C.green}all usable{C.reset}" if bad == 0 else f"{C.red}{share:.0f}% spoiled{C.reset}"
        emit(f"  {ch.color}{ch.name:<8}{C.reset} "
             f"carried {ch.attempt_rate_hz():6.2f} Hz ({ch.attempts():4d}), "
             f"usable {ch.rate_hz():6.2f} Hz ({ch.ok:4d})   "
             f"{ch.anomalies:4d} contaminated, {ch.timeouts:3d} timeouts   {verdict}")

    carried = total_attempts / wall_clock if wall_clock > 0 else 0.0
    combined = total_ok / wall_clock if wall_clock > 0 else 0.0
    emit(f"\n  Combined carried throughput: {C.bold}{carried:.2f} Hz{C.reset} over {wall_clock:.2f}s")
    emit(f"  Combined usable throughput : {C.bold}{combined:.2f} Hz{C.reset}")

    if mode in ("duplex", "zoom"):
        emit(f"\n  Per-channel target for full duplex: {TARGET_HZ} Hz each")
        for ch in channels:
            mark = f"{C.green}meets{C.reset}" if ch.attempt_rate_hz() >= TARGET_HZ else f"{C.red}below{C.reset}"
            emit(f"    {ch.name:<8} carried {ch.attempt_rate_hz():6.2f} Hz  {mark} target "
                 f"{C.dim}(throughput limit){C.reset}")
        emit(f"  {C.dim}A channel can miss the target on carried rate (too slow) or on{C.reset}")
        emit(f"  {C.dim}usable rate (fast enough, but replies unusable). These are{C.reset}")
        emit(f"  {C.dim}separate defects with separate fixes.{C.reset}")

    if sampler:
        emit(f"\n  UART status sampled {sampler.samples} times; "
             f"busy_tx and busy_rx asserted simultaneously: "
             f"{C.bold}{sampler.both_busy}{C.reset} times")
        if sampler.both_busy == 0 and sampler.samples > 0:
            emit(f"  {C.dim}Never both busy at once => the link moves data one "
                 f"direction at a time (half duplex).{C.reset}")

    if total_bad:
        emit(f"\n  {C.red}{total_bad} replies were contaminated or missing.{C.reset}")
        emit(f"  {C.dim}A contaminated reply is one holding bytes that belong to a different{C.reset}")
        emit(f"  {C.dim}exchange - typically a zoom Completion (90 5z FF) that arrived long{C.reset}")
        emit(f"  {C.dim}after transceive() returned, then surfaced inside a later read.{C.reset}")
    else:
        emit(f"\n  {C.green}No contaminated or missing replies in this run.{C.reset}")


#######################################################################################

def main():
    parser = argparse.ArgumentParser(
        description="Watch VISCA duplex behaviour on the LVDS serial link, live.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("mode", choices=sorted(MODES), help="which experiment to run")
    parser.add_argument("-d", "--dev", default=None, help="device path (default: autodetect)")
    parser.add_argument("-t", "--duration", type=float, default=3.0,
                        help="seconds to run, for seq/duplex/zoom (default: 3.0)")
    parser.add_argument("-i", "--interval", type=float, default=0.0,
                        help="pause between requests in seconds, 0 = flat out (default: 0)")
    parser.add_argument("--scales", type=int, nargs="+", default=[1, 10],
                        help="zoom table scales to alternate between (default: 1 10)")
    parser.add_argument("--cycles", type=int, default=4,
                        help="probe mode: how many write+read cycles (default: 4)")
    parser.add_argument("--reads", type=int, default=3,
                        help="probe mode: reads after each write (default: 3)")
    parser.add_argument("--burst", type=int, default=4,
                        help="sockets mode: commands to fire back to back (default: 4)")
    parser.add_argument("--gap", type=float, default=15.0,
                        help="sockets mode: ms to listen between sends (default: 15)")
    parser.add_argument("--drain", type=float, default=3.0,
                        help="sockets/cancel mode: seconds to listen afterwards (default: 3)")
    parser.add_argument("--uart", action="store_true",
                        help="also sample the FPGA busy_tx/busy_rx bits during the run")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="suppress the per-transaction log, print only the summary")
    args = parser.parse_args()

    device_path = args.dev
    if device_path is None:
        found = glob.glob("/dev/links/lvds*")
        device_path = found[0] if found else "/dev/v4l-subdev1"

    inquiry, commands, zoom_table = load_visca()

    for scale in args.scales:
        if str(scale) not in zoom_table:
            parser.error(f"scale {scale} is not in the zoom table "
                         f"(valid: {', '.join(sorted(zoom_table, key=int))})")

    device = LvdsSerial(device_path)

    banner("LVDS VISCA duplex monitor")
    emit(f"  device   : {device_path}")
    emit(f"  baud     : {device.get_baud()}")
    emit(f"  mode     : {args.mode}")
    if args.mode == "probe":
        emit(f"  cycles   : {args.cycles} x (1 write + {args.reads} reads), scales {args.scales}")
    else:
        emit(f"  duration : {args.duration:.1f}s per channel"
             f"{'' if args.interval == 0 else f', paced {args.interval * 1000:.0f} ms apart'}")

    probe = device.transceive(bytearray.fromhex(inquiry["camera_info"]), start_wait_ms=TIMEOUT)
    if not probe:
        emit(f"\n{C.red}No reply to camera_info - is the camera connected and powered?{C.reset}")
        return 1
    summary, _ = decode_reply(probe)
    emit(f"  camera   : {probe.hex()}  ({summary})")

    sampler = None
    if args.uart:
        sampler = UartSampler(device)
        sampler.start()

    try:
        result = MODES[args.mode](device, args, inquiry, commands, zoom_table)
    finally:
        if sampler:
            sampler.stop()

    if args.mode in RAW_MODES:
        print_raw_summary(result, sampler)
    else:
        channels, wall_clock = result
        print_summary(channels, wall_clock, sampler, args.mode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
