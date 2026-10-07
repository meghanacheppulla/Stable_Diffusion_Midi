🎵 Pleasant Music Studio
A Tkinter desktop app that composes a pleasant piece of music, shows its notes, draws a piano roll, and plays the audio — with no FluidSynth or soundfont needed. It can also open any MIDI file (for example from the MAESTRO dataset) and play it.
✨ Features
Generate New Music – composes a fresh song (melody, arpeggio, pad, bass) and plays it automatically
4 moods – Calm Piano (C major), Happy Morning (G major), Dreamy Night (D major), Soft & Emotional (A minor)
Adjustable length – 8 to 32 bars
Note table – first 10 notes per instrument: note name, MIDI number, start, end, velocity
Piano roll – colour-coded notes with a moving playhead
Open MIDI – load any `.mid` / `.midi` file (first 90 seconds are rendered)
Save WAV / Save MIDI – export your song
Built-in synthesizer – piano-like tones, soft pad and reverb, written with NumPy
📁 Project Structure
```
PleasantMusicStudio/
├── main.py             # Tkinter GUI (window, buttons, playback, piano roll)
├── music_engine.py     # Composer, synthesizer, WAV/MIDI reading and writing
├── requirements.txt
├── run_windows.bat     # Double-click launcher (Windows)
├── run_mac_linux.sh    # Launcher (macOS / Linux)
└── README.md
```
🚀 Getting Started
Requirements
Python 3.8 or newer
`numpy`
(Optional, for the Open MIDI button) `pretty_midi` and `setuptools`
Run
```bash
pip install numpy
python main.py
```
On Windows you can also double-click `run_windows.bat`.
To use Open MIDI:
```bash
pip install pretty_midi setuptools
```
Linux notes
```bash
sudo apt install python3-tk        # if Tkinter is missing
```
Sound playback uses whichever of `paplay`, `aplay`, `play` or `ffplay` is installed.
🎹 How to Use
Start the app — a song is generated and starts playing right away.
Choose a Mood and Length, then click Generate New Music for a new song.
Use Play / Stop to control playback.
Click Open MIDI to play a MIDI file such as one from MAESTRO.
Click Save WAV or Save MIDI to keep your music.
🔧 How It Works
Composer (`compose`) picks a chord progression for the chosen mood and builds the bass, pad, arpeggio and melody. The melody lands on chord tones on strong beats and moves by small steps elsewhere, which keeps it smooth and pleasant.
Synthesizer (`synthesize`) turns every note into sound using harmonic additive synthesis (piano-like decay), a slow-attack pad, and a light reverb, then normalizes the volume and fades out.
Player uses `winsound` on Windows, `afplay` on macOS, and a system player on Linux, so no extra audio libraries are needed.
🛠 Troubleshooting
Problem	Fix
`No module named numpy`	`pip install numpy`
`No module named tkinter` (Linux)	`sudo apt install python3-tk`
Open MIDI shows an error	`pip install pretty_midi setuptools`
No sound on Linux	Install `pulseaudio-utils` (paplay), `alsa-utils` (aplay) or `ffmpeg` (ffplay), or use Save WAV
