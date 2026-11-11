"""Frontier Wire's news music, generated in code (original, no samples, nothing to license).

    theme(total, scene_starts, out)  -> a WAV the length of the recap: an opening sting, a quiet driving bed
                                        (pad, pulsing bass, ticking hats), a soft whoosh into each story and a
                                        closing hit that rings out. The render ducks it under the voice.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 112
BEAT = 60 / BPM
# A minor: Am - F - C - G, two bars each
CHORDS = [(45, [57, 60, 64, 69]), (41, [57, 60, 65, 69]), (48, [55, 60, 64, 67]), (43, [55, 59, 62, 67])]


def _hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _lowpass_fast(x: np.ndarray, cutoff: float, block: int = 256) -> np.ndarray:
    """One-pole lowpass via scipy-free recursion in blocks (vectorised per block with a carried state)."""
    a = np.exp(-2 * np.pi * cutoff / SR)
    b = 1 - a
    out = np.empty_like(x)
    state = 0.0
    powers = a ** np.arange(1, block + 1)
    for s in range(0, len(x), block):
        seg = x[s:s + block]
        n = len(seg)
        p = powers[:n]
        # y[k] = a^(k+1) * state + b * sum_{j<=k} a^(k-j) x[j]
        scaled = seg / (a ** np.arange(n))
        conv = np.cumsum(scaled) * (a ** np.arange(n))
        y = p * state + b * conv
        out[s:s + n] = y
        state = y[-1]
    return out


def _saw(freq: float, t: np.ndarray) -> np.ndarray:
    ph = (t * freq) % 1.0
    return 2 * ph - 1


def _env(n: int, attack: float, release: float) -> np.ndarray:
    e = np.ones(n)
    a, r = int(attack * SR), int(release * SR)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def _add(buf: np.ndarray, sig: np.ndarray, at: float) -> None:
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i]


def _pad(total: float) -> np.ndarray:
    out = np.zeros(int(total * SR) + SR)
    seg = 8 * BEAT
    t0, k = 0.0, 0
    while t0 < total:
        _, notes = CHORDS[k % len(CHORDS)]
        n = int((seg + 0.6) * SR)
        t = np.arange(n) / SR
        sig = sum(_saw(_hz(m), t) + _saw(_hz(m) * 1.004, t) for m in notes) / (2 * len(notes))
        _add(out, sig * _env(n, 0.4, 0.6), t0)
        t0 += seg
        k += 1
    return _lowpass_fast(out, 900) * 0.55


def _bass(total: float) -> np.ndarray:
    out = np.zeros(int(total * SR) + SR)
    step = BEAT / 2
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    env = np.exp(-t / 0.07)
    i = 0
    while i * step < total:
        root, _ = CHORDS[int(i * step // (8 * BEAT)) % len(CHORDS)]
        f = _hz(root)
        sig = (np.sin(2 * np.pi * f * t) + 0.3 * _saw(f, t)) * env
        _add(out, sig * (1.0 if i % 2 == 0 else 0.7), i * step)
        i += 1
    return _lowpass_fast(out, 500) * 0.5


def _hats(total: float, rng: np.random.Generator) -> np.ndarray:
    out = np.zeros(int(total * SR) + SR)
    step = BEAT / 4
    n = int(0.05 * SR)
    t = np.arange(n) / SR
    i = 0
    while i * step < total:
        noise = rng.standard_normal(n)
        hp = np.diff(noise, prepend=0)  # crude high-pass
        acc = 1.0 if i % 4 == 2 else 0.45
        _add(out, hp * np.exp(-t / 0.012) * acc, i * step)
        i += 1
    return out * 0.06


def _kick(total: float) -> np.ndarray:
    out = np.zeros(int(total * SR) + SR)
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    f = 50 + 70 * np.exp(-t / 0.03)
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.12)
    b = 0
    while b * BEAT < total:
        if b % 2 == 0:
            _add(out, sig, b * BEAT)
        b += 1
    return out * 0.35


def _hit(rng: np.random.Generator, length: float = 2.5, bright: float = 1.0) -> np.ndarray:
    """A news 'stab': a bright chord, a low boom and a cymbal wash."""
    n = int(length * SR)
    t = np.arange(n) / SR
    chord = sum(_saw(_hz(m + 12), t) + _saw(_hz(m + 12) * 1.006, t) for m in (57, 64, 69, 72)) / 8
    chord = _lowpass_fast(chord, 2500 * bright) * np.exp(-t / 0.6)
    f = 45 + 110 * np.exp(-t / 0.05)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.5)
    cym = np.diff(rng.standard_normal(n), prepend=0) * np.exp(-t / 0.9) * 0.25
    return chord * 0.9 + boom * 0.9 + cym


def _riser(rng: np.random.Generator, length: float) -> np.ndarray:
    n = int(length * SR)
    t = np.linspace(0, 1, n)
    noise = _lowpass_fast(rng.standard_normal(n), 3000)
    return noise * t ** 2.5 * 0.5


def _whoosh(rng: np.random.Generator, length: float = 0.6) -> np.ndarray:
    n = int(length * SR)
    t = np.linspace(0, 1, n)
    noise = _lowpass_fast(rng.standard_normal(n), 1800)
    return noise * np.sin(np.pi * t) ** 2 * 0.35


def theme(total: float, starts: list[float], out: Path) -> Path:
    """`starts`: scene start times [0 (open), story 1..n, outro]."""
    rng = np.random.default_rng(7)
    n = int(total * SR)
    bed = (_pad(total) + _bass(total) + _hats(total, rng) + _kick(total))[:n]
    # bed comes in after the sting and fades out under the closing hit
    fade = np.ones(n)
    a0, a1 = int(0.9 * SR), int(2.4 * SR)
    fade[:a0] = 0
    fade[a0:a1] = np.linspace(0, 1, a1 - a0)
    o = int(starts[-1] * SR)
    fade[o:] = np.linspace(1, 0, n - o) ** 2 if n > o else fade[o:]
    mix = bed * fade * 0.8
    sfx = np.zeros(n + 3 * SR)
    _add(sfx, _riser(rng, 0.5), 0.0)
    _add(sfx, _hit(rng), 0.45)
    for s in starts[1:-1]:
        _add(sfx, _whoosh(rng), max(0.0, s - 0.3))
    _add(sfx, _hit(rng, 3.0, bright=0.8), starts[-1] + 0.1)
    mix = mix + sfx[:n]
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.7
    pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out
