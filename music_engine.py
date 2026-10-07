"""
music_engine.py
---------------
Everything that is NOT the GUI:
  * composing a pleasant piece (notes)
  * turning notes into audio (built-in synthesizer, no FluidSynth needed)
  * saving WAV and MIDI files
  * loading an existing MIDI file (optional, needs `pretty_midi`)

A note is a tuple: (pitch, start_sec, end_sec, velocity, instrument)
instrument is one of: "melody", "arpeggio", "bass", "pad", "piano"
"""

import random
import struct
import wave

import numpy as np

SAMPLE_RATE = 44100

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_name(pitch):
    """60 -> 'C4' (same style as pretty_midi.note_number_to_name)."""
    return f"{NOTE_NAMES[pitch % 12]}{pitch // 12 - 1}"


# ----------------------------------------------------------------------
# 1. COMPOSER
# ----------------------------------------------------------------------
MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]

# name -> (tonic MIDI note, scale, list of progressions (scale degrees), bpm)
MOODS = {
    "Calm Piano (C major)": (60, MAJOR, [[0, 4, 5, 3], [0, 5, 3, 4]], 72),
    "Happy Morning (G major)": (67, MAJOR, [[0, 4, 5, 3], [0, 3, 4, 3]], 92),
    "Dreamy Night (D major)": (62, MAJOR, [[0, 5, 3, 4], [5, 3, 0, 4]], 66),
    "Soft & Emotional (A minor)": (69, MINOR, [[0, 5, 2, 6], [0, 3, 5, 4]], 70),
}


def _pitch(tonic, scale, index):
    """Scale-degree index (can be negative / above 6) -> MIDI pitch."""
    octave, degree = divmod(index, 7)
    return tonic + scale[degree] + 12 * octave


def compose(mood="Calm Piano (C major)", bars=16, seed=None):
    """Create a gentle, pleasant piece. Returns (notes, bpm)."""
    rng = random.Random(seed)
    tonic, scale, progressions, bpm = MOODS[mood]
    tonic_low = tonic - 12 if tonic >= 66 else tonic  # keep range comfortable
    progression = rng.choice(progressions)
    beat = 60.0 / bpm
    bar_len = 4 * beat

    rhythms = [
        [1, 1, 1, 1],
        [1.5, 0.5, 1, 1],
        [2, 1, 1],
        [1, 0.5, 0.5, 2],
        [0.5, 0.5, 1, 2],
        [1, 1, 2],
        [0.5, 0.5, 0.5, 0.5, 2],
    ]

    notes = []
    melody_idx = 9  # starting scale index (about an octave above tonic)

    for bar in range(bars):
        t0 = bar * bar_len
        last_bar = bar == bars - 1
        degree = 0 if last_bar else progression[bar % len(progression)]
        chord = [degree, degree + 2, degree + 4]

        # --- bass: one long root note per bar
        bass = _pitch(tonic_low, scale, degree - 14)
        notes.append((bass, t0, t0 + bar_len * (1.0 if not last_bar else 1.6),
                      62, "bass"))

        # --- pad: soft sustained chord
        for c in chord:
            p = _pitch(tonic_low, scale, c - 7)
            notes.append((p, t0, t0 + bar_len * (1.02 if not last_bar else 1.7),
                          38, "pad"))

        # --- arpeggio: gentle eighth notes
        if last_bar:
            for i, c in enumerate(chord + [chord[0] + 7]):
                p = _pitch(tonic_low, scale, c)
                notes.append((p, t0 + i * beat * 0.5, t0 + i * beat * 0.5 + beat * 2.5,
                              52, "arpeggio"))
        else:
            pattern = [0, 1, 2, 1, 0, 1, 2, 1]
            for i, k in enumerate(pattern):
                p = _pitch(tonic_low, scale, chord[k])
                s = t0 + i * beat * 0.5
                notes.append((p, s, s + beat * 0.9, 50 + (8 if i % 4 == 0 else 0),
                              "arpeggio"))

        # --- melody: enters after 4 bars
        if bar >= 4:
            if last_bar:
                notes.append((_pitch(tonic_low, scale, 7), t0, t0 + bar_len * 1.6,
                              78, "melody"))
                continue
            pattern = rng.choice(rhythms)
            t = t0
            for n_i, dur in enumerate(pattern):
                if n_i == 0:
                    # strong beat: move to nearest chord tone
                    targets = []
                    for c in chord:
                        for shift in (0, 7, 14):
                            targets.append(c + shift)
                    targets = [x for x in targets if 7 <= x <= 14]
                    melody_idx = min(targets, key=lambda x: abs(x - melody_idx))
                else:
                    melody_idx += rng.choice([-2, -1, -1, 0, 1, 1, 2])
                    melody_idx = max(7, min(14, melody_idx))
                p = _pitch(tonic_low, scale, melody_idx)
                start = t + rng.uniform(-0.008, 0.008) if t > 0 else t
                notes.append((p, max(0.0, start), t + dur * beat * 0.97,
                              rng.randint(70, 86), "melody"))
                t += dur * beat

    return notes, bpm


# ----------------------------------------------------------------------
# 2. SYNTHESIZER
# ----------------------------------------------------------------------
def _render_note(pitch, dur, vel, inst):
    freq = 440.0 * 2 ** ((pitch - 69) / 12.0)
    release = 0.35 if inst != "pad" else 0.9
    total = dur + release
    n = int(total * SAMPLE_RATE)
    if n <= 0:
        return np.zeros(0, dtype=np.float32)
    t = np.arange(n) / SAMPLE_RATE
    amp = (vel / 127.0) ** 1.2

    if inst == "pad":
        # warm, slowly swelling sound (slightly detuned sines)
        wave_ = (np.sin(2 * np.pi * freq * t)
                 + 0.6 * np.sin(2 * np.pi * freq * 1.004 * t)
                 + 0.25 * np.sin(2 * np.pi * freq * 2 * t))
        attack = np.clip(t / 0.6, 0, 1)
        env = attack
        wave_ *= 0.45
    else:
        # piano-like: a few harmonics that die away at different speeds
        base_decay = 1.2 + max(0, pitch - 48) * 0.035
        if inst == "bass":
            base_decay = 0.9
        wave_ = np.zeros(n)
        for k in range(1, 8):
            hf = freq * k * (1 + 0.0004 * k * k)  # tiny inharmonicity
            if hf > SAMPLE_RATE / 2.2:
                break
            wave_ += (1.0 / k ** 1.15) * np.exp(-t * (k - 1) * 0.9) * np.sin(2 * np.pi * hf * t)
        attack = np.clip(t / 0.004, 0, 1)
        env = attack * np.exp(-t * base_decay)

    # note-off fade
    off = np.ones(n)
    rel_start = int(dur * SAMPLE_RATE)
    rel_n = n - rel_start
    if rel_n > 0:
        off[rel_start:] = np.linspace(1.0, 0.0, rel_n) ** 2
    return (wave_ * env * off * amp).astype(np.float32)


def _reverb(signal, amount=0.22):
    """Cheap room reverb made from decaying noise."""
    rng = np.random.default_rng(1)
    length = int(1.3 * SAMPLE_RATE)
    t = np.arange(length) / SAMPLE_RATE
    ir = rng.standard_normal(length) * np.exp(-t / 0.28)
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    size = 1
    while size < len(signal) + length:
        size *= 2
    wet = np.fft.irfft(np.fft.rfft(signal, size) * np.fft.rfft(ir, size), size)[:len(signal)]
    return (1 - amount) * signal + amount * wet * 1.2


def synthesize(notes, max_seconds=None, progress=None):
    """Notes -> float32 mono audio array (-1..1)."""
    if max_seconds is not None:
        notes = [n for n in notes if n[1] < max_seconds]
    if not notes:
        return np.zeros(SAMPLE_RATE, dtype=np.float32)
    end = max(n[2] for n in notes)
    if max_seconds is not None:
        end = min(end, max_seconds)
    total = int((end + 2.0) * SAMPLE_RATE)
    mix = np.zeros(total, dtype=np.float32)
    count = len(notes)
    for i, (pitch, start, stop, vel, inst) in enumerate(notes):
        stop = min(stop, end)
        seg = _render_note(pitch, max(0.05, stop - start), vel, inst)
        s = int(start * SAMPLE_RATE)
        e = min(total, s + len(seg))
        if e > s:
            mix[s:e] += seg[:e - s]
        if progress and i % 20 == 0:
            progress(i / count)
    mix = _reverb(mix)
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = mix / peak * 0.85
    # soft fade-out at the very end
    fade = int(1.0 * SAMPLE_RATE)
    mix[-fade:] *= np.linspace(1, 0, fade)
    return mix.astype(np.float32)


def save_wav(audio, path):
    data = np.clip(audio, -1, 1)
    pcm = (data * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())


# ----------------------------------------------------------------------
# 3. MIDI WRITE / READ
# ----------------------------------------------------------------------
def _varlen(value):
    value = int(value)
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(out))


_CHANNELS = {"melody": (0, 0), "arpeggio": (0, 0), "piano": (0, 0),
             "pad": (1, 89), "bass": (2, 32)}  # inst -> (channel, GM program)


def save_midi(notes, bpm, path):
    """Write a standard MIDI file (no extra libraries needed)."""
    ppq = 480
    tick_per_sec = ppq * bpm / 60.0
    events = []  # (tick, order, bytes)
    for ch, prog in {(1, 89), (2, 32), (0, 0)}:
        events.append((0, 0, bytes([0xC0 | ch, prog])))
    for pitch, start, stop, vel, inst in notes:
        ch, _ = _CHANNELS.get(inst, (0, 0))
        pitch = max(0, min(127, int(pitch)))
        vel = max(1, min(127, int(vel)))
        events.append((round(start * tick_per_sec), 2, bytes([0x90 | ch, pitch, vel])))
        events.append((round(stop * tick_per_sec), 1, bytes([0x80 | ch, pitch, 0])))
    events.sort(key=lambda e: (e[0], e[1]))

    track = bytearray()
    micros = int(60_000_000 / bpm)
    track += b"\x00\xFF\x51\x03" + micros.to_bytes(3, "big")
    last = 0
    for tick, _, data in events:
        track += _varlen(tick - last) + data
        last = tick
    track += b"\x00\xFF\x2F\x00"

    with open(path, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq))
        f.write(b"MTrk" + struct.pack(">I", len(track)) + bytes(track))


def load_midi(path):
    """Read a .mid/.midi file (e.g. from MAESTRO). Needs `pip install pretty_midi`."""
    try:
        import pretty_midi
    except Exception as exc:  # ImportError or pkg_resources problems
        raise RuntimeError(
            "Opening MIDI files needs the 'pretty_midi' package.\n"
            "Install it with:  pip install pretty_midi setuptools\n\n"
            f"({exc})")
    midi = pretty_midi.PrettyMIDI(path)
    notes = []
    for instrument in midi.instruments:
        if instrument.is_drum:
            continue
        for n in instrument.notes:
            notes.append((n.pitch, n.start, n.end, n.velocity, "piano"))
    notes.sort(key=lambda n: n[1])
    if not notes:
        raise RuntimeError("This MIDI file contains no playable notes.")
    return notes
