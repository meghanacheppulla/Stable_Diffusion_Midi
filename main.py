"""
Pleasant Music Studio  -  Tkinter desktop app
Run:  python main.py

Generates a pleasant piece of music (or loads a MIDI file such as one from the
MAESTRO dataset), shows the notes, draws a piano roll and plays the audio.
Works on Windows, macOS and Linux. Only `numpy` is required.
"""

import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import music_engine as me

COLORS = {"melody": "#e4572e", "arpeggio": "#29a0b1", "bass": "#4f5d75",
          "pad": "#a98467", "piano": "#e4572e"}
LABELS = {"melody": "Melody", "arpeggio": "Arpeggio", "bass": "Bass",
          "pad": "Pad", "piano": "Piano"}


# ----------------------------------------------------------------------
# Audio playback (no extra libraries)
# ----------------------------------------------------------------------
class Player:
    def __init__(self):
        self.proc = None

    def play(self, wav_path):
        self.stop()
        if sys.platform.startswith("win"):
            import winsound
            winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return True
        if sys.platform == "darwin":
            cmd = ["afplay", wav_path]
        else:
            cmd = None
            for tool, args in (("paplay", []), ("aplay", ["-q"]),
                               ("play", ["-q"]),
                               ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet"])):
                if shutil.which(tool):
                    cmd = [tool] + args + [wav_path]
                    break
        if not cmd:
            return False
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        return True

    def stop(self):
        if sys.platform.startswith("win"):
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        if self.proc is not None:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None


# ----------------------------------------------------------------------
# Main window
# ----------------------------------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        root.title("Pleasant Music Studio")
        root.geometry("900x690")
        root.minsize(760, 600)

        self.player = Player()
        self.notes = []
        self.bpm = 72
        self.audio = None
        self.duration = 0.0
        self.wav_path = os.path.join(tempfile.gettempdir(), "pleasant_music_preview.wav")
        self.play_started = None
        self.busy = False
        self.q = queue.Queue()

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self._poll)
        self.generate()  # make a first song right away

    # ---------------- UI ----------------
    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Big.TButton", font=("Segoe UI", 10, "bold"), padding=6)

        top = ttk.Frame(self.root, padding=(14, 12, 14, 4))
        top.pack(fill="x")
        ttk.Label(top, text="\u266B Pleasant Music Studio", style="Title.TLabel").pack(side="left")

        opts = ttk.Frame(self.root, padding=(14, 4))
        opts.pack(fill="x")
        ttk.Label(opts, text="Mood:").pack(side="left")
        self.mood = tk.StringVar(value=list(me.MOODS)[0])
        ttk.Combobox(opts, textvariable=self.mood, values=list(me.MOODS),
                     state="readonly", width=28).pack(side="left", padx=(6, 16))
        ttk.Label(opts, text="Length (bars):").pack(side="left")
        self.bars = tk.IntVar(value=16)
        ttk.Spinbox(opts, from_=8, to=32, increment=4, textvariable=self.bars,
                    width=5, state="readonly").pack(side="left", padx=(6, 0))

        btns = ttk.Frame(self.root, padding=(14, 8))
        btns.pack(fill="x")
        self.b_gen = ttk.Button(btns, text="\u2728 Generate New Music", style="Big.TButton",
                                command=self.generate)
        self.b_gen.pack(side="left", padx=(0, 6))
        self.b_open = ttk.Button(btns, text="\U0001F4C2 Open MIDI", style="Big.TButton",
                                 command=self.open_midi)
        self.b_open.pack(side="left", padx=6)
        self.b_play = ttk.Button(btns, text="\u25B6 Play", style="Big.TButton",
                                 command=self.play)
        self.b_play.pack(side="left", padx=6)
        self.b_stop = ttk.Button(btns, text="\u25A0 Stop", style="Big.TButton",
                                 command=self.stop)
        self.b_stop.pack(side="left", padx=6)
        self.b_wav = ttk.Button(btns, text="Save WAV", command=self.save_wav)
        self.b_wav.pack(side="left", padx=6)
        self.b_mid = ttk.Button(btns, text="Save MIDI", command=self.save_midi)
        self.b_mid.pack(side="left", padx=6)

        self.status = tk.StringVar(value="Starting...")
        ttk.Label(self.root, textvariable=self.status, padding=(14, 0)).pack(anchor="w")
        self.progress = ttk.Progressbar(self.root, mode="determinate", maximum=1000)
        self.progress.pack(fill="x", padx=14, pady=(4, 6))

        # piano roll
        roll_frame = ttk.LabelFrame(self.root, text=" Piano roll ", padding=6)
        roll_frame.pack(fill="x", padx=14, pady=4)
        self.canvas = tk.Canvas(roll_frame, height=170, bg="#14213d", highlightthickness=0)
        self.canvas.pack(fill="x")
        self.canvas.bind("<Configure>", lambda e: self.draw_roll())

        # note table
        table_frame = ttk.LabelFrame(self.root, text=" First 10 notes of each instrument ",
                                     padding=6)
        table_frame.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        cols = ("inst", "note", "midi", "start", "end", "vel")
        heads = ("Instrument", "Note", "MIDI", "Start (s)", "End (s)", "Velocity")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=8)
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=110, anchor="center")
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    # ---------------- helpers ----------------
    def set_busy(self, busy, text=None):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for b in (self.b_gen, self.b_open, self.b_play, self.b_wav, self.b_mid):
            b.configure(state=state)
        if text:
            self.status.set(text)

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "progress":
                    self.progress["value"] = payload * 1000
                elif kind == "done":
                    self._on_ready(*payload)
                elif kind == "error":
                    self.set_busy(False, "Something went wrong.")
                    self.progress["value"] = 0
                    messagebox.showerror("Error", payload)
        except queue.Empty:
            pass
        # playback progress / playhead
        if self.play_started is not None:
            elapsed = time.time() - self.play_started
            if elapsed >= self.duration:
                self.play_started = None
                self.progress["value"] = 0
                self.status.set("Finished playing.")
                self.draw_roll()
            else:
                self.progress["value"] = elapsed / self.duration * 1000
                self.draw_roll(playhead=elapsed)
        self.root.after(100, self._poll)

    # ---------------- actions ----------------
    def _render_async(self, notes, bpm, label, max_seconds=None):
        self.stop()
        self.set_busy(True, f"Creating audio ({label})... please wait")
        self.progress["value"] = 0

        def work():
            try:
                audio = me.synthesize(
                    notes, max_seconds=max_seconds,
                    progress=lambda f: self.q.put(("progress", f)))
                me.save_wav(audio, self.wav_path)
                self.q.put(("done", (notes, bpm, audio, label)))
            except Exception as exc:  # show any problem in a dialog
                self.q.put(("error", f"{type(exc).__name__}: {exc}"))

        threading.Thread(target=work, daemon=True).start()

    def generate(self):
        if self.busy:
            return
        try:
            bars = int(self.bars.get())
        except (tk.TclError, ValueError):
            bars = 16
        notes, bpm = me.compose(self.mood.get(), bars=bars)
        self._render_async(notes, bpm, self.mood.get())

    def open_midi(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(
            title="Choose a MIDI file",
            filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")])
        if not path:
            return
        try:
            notes = me.load_midi(path)
        except Exception as exc:
            messagebox.showerror("Cannot open MIDI", str(exc))
            return
        messagebox.showinfo(
            "Long file?", "Only the first 90 seconds will be turned into audio "
                          "to keep things fast.")
        self._render_async(notes, 120, os.path.basename(path), max_seconds=90)

    def _on_ready(self, notes, bpm, audio, label):
        self.notes, self.bpm, self.audio = notes, bpm, audio
        self.duration = len(audio) / me.SAMPLE_RATE
        self.set_busy(False,
                      f"Ready: {label}  |  {len(notes)} notes  |  {self.duration:.0f} sec  "
                      f"-  press Play")
        self.progress["value"] = 0
        self.fill_table()
        self.draw_roll()
        self.play()  # start automatically so you hear it at once

    def play(self):
        if self.audio is None or self.busy:
            return
        if not os.path.exists(self.wav_path):
            me.save_wav(self.audio, self.wav_path)
        if self.player.play(self.wav_path):
            self.play_started = time.time()
            self.status.set("Playing...")
        else:
            messagebox.showinfo(
                "No audio player found",
                "Could not find a sound player on this system.\n"
                "Use 'Save WAV' and open the file with any media player.")

    def stop(self):
        self.player.stop()
        self.play_started = None
        self.progress["value"] = 0
        if self.audio is not None:
            self.status.set("Stopped.")
        self.draw_roll()

    def save_wav(self):
        if self.audio is None:
            return
        path = filedialog.asksaveasfilename(defaultextension=".wav",
                                            initialfile="my_music.wav",
                                            filetypes=[("WAV audio", "*.wav")])
        if path:
            me.save_wav(self.audio, path)
            messagebox.showinfo("Saved", f"Saved:\n{path}")

    def save_midi(self):
        if not self.notes:
            return
        path = filedialog.asksaveasfilename(defaultextension=".mid",
                                            initialfile="my_music.mid",
                                            filetypes=[("MIDI file", "*.mid")])
        if path:
            me.save_midi(self.notes, self.bpm, path)
            messagebox.showinfo("Saved", f"Saved:\n{path}")

    # ---------------- display ----------------
    def fill_table(self):
        self.tree.delete(*self.tree.get_children())
        shown = {}
        for pitch, start, end, vel, inst in sorted(self.notes, key=lambda n: n[1]):
            if shown.get(inst, 0) >= 10:
                continue
            shown[inst] = shown.get(inst, 0) + 1
            self.tree.insert("", "end", values=(
                LABELS.get(inst, inst), me.note_name(pitch), pitch,
                round(start, 2), round(end, 2), vel))

    def draw_roll(self, playhead=None):
        c = self.canvas
        c.delete("all")
        if not self.notes:
            return
        w = max(c.winfo_width(), 100)
        h = max(c.winfo_height(), 50)
        total = max(self.duration, max(n[2] for n in self.notes), 1.0)
        lo = min(n[0] for n in self.notes)
        hi = max(n[0] for n in self.notes)
        span = max(hi - lo, 12)
        for pitch, start, end, vel, inst in self.notes:
            x1 = start / total * w
            x2 = max(x1 + 2, min(end, total) / total * w)
            y = h - 8 - (pitch - lo) / span * (h - 16)
            c.create_rectangle(x1, y - 2, x2, y + 2, fill=COLORS.get(inst, "#ffffff"),
                               outline="")
        if playhead is not None:
            x = min(playhead / total, 1.0) * w
            c.create_line(x, 0, x, h, fill="#ffffff", width=2)

    def on_close(self):
        self.player.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
