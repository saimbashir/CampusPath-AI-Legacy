"""Create a private virtual environment and install the pinned application dependencies."""
import hashlib,os,subprocess,sys,venv
from pathlib import Path
root=Path(__file__).resolve().parents[1];os.chdir(root)
if sys.version_info<(3,12):raise SystemExit('CampusPath needs Python 3.12 or newer. Install Python 3.12 and try again.')
folder=root/'.venv';python=folder/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
if not python.exists():
    print('Creating the local Python environment...',flush=True);venv.EnvBuilder(with_pip=True).create(folder)
lock=root/'requirements.lock.txt';fingerprint=hashlib.sha256(lock.read_bytes()).hexdigest();marker=folder/'.campuspath-dependencies'
if not marker.exists() or marker.read_text()!=fingerprint:
    print('Installing packages. Internet is required for this first setup...',flush=True)
    subprocess.run([str(python),'-m','pip','install','-r',str(lock)],check=True)
    marker.write_text(fingerprint)
raise SystemExit(subprocess.call([str(python),str(root/'run.py'),*sys.argv[1:]]))
