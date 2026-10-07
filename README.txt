PLEASANT MUSIC STUDIO  (Tkinter)
================================
Generates a pleasant song, shows its notes + a piano roll, and plays it.

HOW TO RUN
1. Install Python 3.8+ (Tkinter is included on Windows/macOS).
2. Open a terminal in this folder and run:
       pip install numpy
       python main.py
   (or double-click run_windows.bat on Windows)

BUTTONS
- Generate New Music : composes a new song in the chosen mood and plays it
- Open MIDI          : load any .mid/.midi file (e.g. MAESTRO) and play it
                       (needs:  pip install pretty_midi setuptools)
- Play / Stop        : control playback
- Save WAV / MIDI    : export the song

NOTES
- No FluidSynth / soundfont needed: the app has its own built-in synthesizer.
- Linux only: if Tkinter is missing, run  sudo apt install python3-tk
  and for sound, have one of: paplay, aplay, or ffplay installed.
