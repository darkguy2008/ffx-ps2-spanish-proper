import os
import subprocess

from tqdm import tqdm

PROGRESS_FD = 'PROGRESS_FD'


def run_steps(steps, label):
    results = []
    for number, (title, step) in enumerate(steps, 1):
        print(f'{label} {number}/{len(steps)}: {title}')
        results.append(step())
    return results


def run_reporting(command, description, cwd=None):
    progress, progress_writer = os.pipe()
    process = subprocess.Popen(command, cwd=cwd, pass_fds=(progress_writer,), env=os.environ | {PROGRESS_FD: str(progress_writer)})
    os.close(progress_writer)
    with os.fdopen(progress) as lines, tqdm(total=int(next(lines, 0)), desc=description, unit='file', leave=False) as bar:
        for _ in lines:
            bar.update()
    if process.wait():
        raise subprocess.CalledProcessError(process.returncode, command)
