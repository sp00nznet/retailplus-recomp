r"""Run the recomp once on the hidden desktop, print its log and the windows it opened.

    py -3 tools/run_hidden.py [--secs N] [-- HOST ARGS...]

For bring-up: a fresh copy of game\ each time, like the harness."""
import os, shutil, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rp  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
secs = int(sys.argv[sys.argv.index('--secs') + 1]) if '--secs' in sys.argv else 30
extra = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
f = tempfile.mkdtemp(prefix='rp_h_')
shutil.copytree(os.path.join(ROOT, 'game'), f, dirs_exist_ok=True)
ini = os.path.join(os.environ['LOCALAPPDATA'], 'VirtualStore', 'Windows', 'pluslite.INI')
if os.path.exists(ini):
    os.remove(ini)
log = os.path.join(ROOT, 'work', 'run.log')
pid = rp.launch('"%s" --run --game "%s" %s' % (os.path.join(ROOT, 'build', 'retailplusrecomp.exe'), f,
                                                ' '.join(extra)), f, log=log)
t = time.time() + secs
while time.time() < t and not rp.tops(pid):
    time.sleep(0.5)
time.sleep(3)
rp.dump(pid)
for i, h in enumerate(rp.tops(pid)):
    rp.snap(h, os.path.join(ROOT, 'work', 'shot_%d.png' % i))
rp.kill(pid)
L = open(log, errors='replace').read().splitlines()
print('\n'.join(L[-40:]))
shutil.rmtree(f, ignore_errors=True)
