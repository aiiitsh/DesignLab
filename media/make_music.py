"""Original royalty-free background track: upbeat 112 BPM electronic pop, 120 s, stereo 44.1 kHz."""
import numpy as np
import wave

SR = 44100
BPM = 112
DUR = 120.0
beat = 60 / BPM
N = int(SR * DUR)
L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(640)

def note_hz(n):  # MIDI -> Hz
    return 440.0 * 2 ** ((n - 69) / 12)

def env(n, a=0.005, d=0.1, s=0.6, r=0.1, length=None):
    length = length or n
    t = np.arange(n) / SR
    e = np.ones(n) * s
    ai = int(a * SR); di = int(d * SR); ri = int(r * SR)
    e[:ai] = np.linspace(0, 1, max(ai, 1))[:len(e[:ai])]
    e[ai:ai + di] = np.linspace(1, s, max(di, 1))[:len(e[ai:ai + di])]
    if ri and ri < n:
        e[-ri:] *= np.linspace(1, 0, ri)
    return e

def add(buf, start, sig, pan=0.0, gain=1.0):
    i = int(start * SR)
    if i >= N: return
    sig = sig[: N - i] * gain
    L[i:i + len(sig)] += sig * np.sqrt((1 - pan) / 2)
    R[i:i + len(sig)] += sig * np.sqrt((1 + pan) / 2)

def saw(f, n, detune=0.0):
    t = np.arange(n) / SR
    out = np.zeros(n)
    for dv in (-detune, 0, detune):
        ph = (t * f * (1 + dv)) % 1.0
        out += 2 * ph - 1
    return out / 3

def lowpass(x, cut):
    a = np.exp(-2 * np.pi * cut / SR)
    y = np.zeros_like(x); prev = 0.0
    for i in range(len(x)):
        prev = (1 - a) * x[i] + a * prev
        y[i] = prev
    return y

def lp_fast(x, cut):  # one-pole via cumulative trick on blocks (vectorized approx: two passes of moving average)
    k = max(1, int(SR / cut / 2))
    ker = np.ones(k) / k
    return np.convolve(np.convolve(x, ker, 'same'), ker, 'same')

# progression (vi-IV-I-V in C major feel): Am F C G, one chord per bar (4 beats)
prog = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]
bass_roots = [45, 41, 36, 43]
bar = 4 * beat
nbars = int(DUR / bar) + 1

def section(b):  # energy by bar
    t = b * bar
    if t < 6: return 0          # title: pad only
    if t < 14: return 1         # + arps, light hats
    if t > DUR - 7: return 0    # outro
    return 2                    # full

# --- pad
for b in range(nbars):
    ch = prog[b % 4]; n = int(bar * SR) + int(0.4 * SR)
    sig = sum(saw(note_hz(m + 12), n, 0.004) for m in ch) / 3
    sig = lp_fast(sig, 1800) * env(n, a=0.35, d=0.4, s=0.8, r=0.5)
    add(None, b * bar, sig, pan=-0.2, gain=0.16)
    add(None, b * bar, sig, pan=0.25, gain=0.12)

# --- pluck arpeggio (16ths)
for b in range(nbars):
    if section(b) == 0: continue
    ch = prog[b % 4]
    pattern = [0, 1, 2, 1, 2, 0, 1, 2, 0, 2, 1, 0, 2, 1, 2, 1]
    for s16, idx in enumerate(pattern):
        m = ch[idx] + 24
        n = int(0.22 * SR)
        t = np.arange(n) / SR
        sig = (np.sin(2 * np.pi * note_hz(m) * t) + 0.35 * np.sin(4 * np.pi * note_hz(m) * t)) * np.exp(-t * 18)
        add(None, b * bar + s16 * beat / 4, sig, pan=0.45 if s16 % 2 else -0.45, gain=0.09)

# --- bass (8ths, octave pump)
for b in range(nbars):
    if section(b) < 2: continue
    root = bass_roots[b % 4]
    for e8 in range(8):
        m = root + (12 if e8 % 2 else 0)
        n = int(beat / 2 * SR * 0.95)
        sig = lp_fast(saw(note_hz(m), n, 0.002), 500) * env(n, a=0.004, d=0.08, s=0.7, r=0.03)
        add(None, b * bar + e8 * beat / 2, sig, gain=0.32)

# --- drums
def kick():
    n = int(0.35 * SR); t = np.arange(n) / SR
    f = 50 + 110 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
def hat(open_=False):
    n = int((0.18 if open_ else 0.05) * SR); t = np.arange(n) / SR
    x = rng.standard_normal(n); x = x - lp_fast(x, 6000)
    return x * np.exp(-t * (20 if open_ else 70))
def clap():
    n = int(0.25 * SR); t = np.arange(n) / SR
    x = rng.standard_normal(n); x = lp_fast(x, 3500) - lp_fast(x, 900)
    e = np.exp(-t * 16); e[: int(.012 * SR)] *= 1.6
    return x * e * 2.2

K, H, HO, C = kick(), hat(), hat(True), clap()
for b in range(nbars):
    sec = section(b)
    for q in range(4):
        t0 = b * bar + q * beat
        if sec == 2:
            add(None, t0, K, gain=0.55)
            if q in (1, 3): add(None, t0, C, gain=0.22)
            add(None, t0 + beat / 2, HO, pan=0.3, gain=0.10)
        if sec >= 1:
            for s in (0.25, 0.75):
                add(None, t0 + s * beat, H, pan=-0.3, gain=0.07)
    # riser into the drop and fills every 8 bars
    if sec == 2 and b % 8 == 7:
        for s16 in range(4):
            add(None, b * bar + 3 * beat + s16 * beat / 4, C, gain=0.12 + 0.03 * s16)

# --- sidechain pump on pad/arp feel: duck whole mix lightly on each beat in full sections
t = np.arange(N) / SR
pump = 1 - 0.18 * np.exp(-((t % beat) / 0.09))
full = np.array([section(int(x // bar)) == 2 for x in t[:: SR // 100]])
mask = np.repeat(full, SR // 100)[:N]
mask = np.pad(mask, (0, N - len(mask)), constant_values=False)
L *= np.where(mask, pump, 1); R *= np.where(mask, pump, 1)

# fades and normalize
fade_in, fade_out = int(1.5 * SR), int(4.0 * SR)
for ch in (L, R):
    ch[:fade_in] *= np.linspace(0, 1, fade_in)
    ch[-fade_out:] *= np.linspace(1, 0, fade_out)
peak = max(np.abs(L).max(), np.abs(R).max())
L /= peak; R /= peak
L = np.tanh(L * 1.2) * 0.89; R = np.tanh(R * 1.2) * 0.89
st = (np.stack([L, R], 1) * 32767).astype(np.int16)
with wave.open('/tmp/claude-0/video/music.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
print('ok', len(st) / SR)
