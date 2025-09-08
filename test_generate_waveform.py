# Small test to exercise generate_waveform without starting full GUI
import os
import sys
import tkinter as tk
import tempfile

# Ensure project path
proj_root = os.path.dirname(__file__)
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)
from Scripts.visor_sesiones import SessionViewerApp

# Create a hidden root and app instance
root = tk.Tk()
root.withdraw()
app = SessionViewerApp(root)

# Try to find an existing temp directory used by a running session (tmppa_*)
tmproot = os.getenv('TEMP') or tempfile.gettempdir()
candidates = []
for name in os.listdir(tmproot):
    if name.startswith('tmppa_'):
        full = os.path.join(tmproot, name)
        if os.path.isdir(full):
            candidates.append((os.path.getmtime(full), full))

if candidates:
    # pick the most recently modified one
    candidates.sort(reverse=True)
    temp_dir = candidates[0][1]
else:
    temp_dir = app.temp_dir

print('Using temp_dir:', temp_dir)

# Find mp3 files
mp3s = []
for root_dir, _, files in os.walk(temp_dir):
    for f in files:
        if f.lower().endswith('.mp3'):
            mp3s.append(os.path.join(root_dir, f))

if not mp3s:
    print('No mp3 files found in temp_dir')
    sys.exit(0)

for p in mp3s[:4]:
    print('Testing:', p)
    ok = app.generate_waveform(p)
    print('Result:', ok)
    if ok and app.waveform_data:
        print('Duration:', app.waveform_data.get('duration'))

print('Done')
