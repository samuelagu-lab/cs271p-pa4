"""Public fresh-process runner for Weighted Stable Garden.

Imports have a separate 10-second wall allowance. Construction/search/answers
have a strict parent wall deadline. Ordinary Python annotations/dataclasses work;
current source is compiled directly, never loaded from a stale .pyc.
"""
import contextlib
import copy
import io
import json
import math
import os
from pathlib import Path
import random
import queue
import signal
import subprocess
import sys
import time
import traceback
import types
import threading

import problem

MAX_MESSAGES = 64
MAX_BYTES = 16 * 1024 * 1024


class LimitedLog(io.StringIO):
    def write(self, text):
        text = str(text)
        remaining = max(0, 6000-self.tell())
        super().write(text[:remaining])
        return len(text)


def snapshot(value, depth=0, counter=None):
    if counter is None:
        counter = [0]
    counter[0] += 1
    if counter[0] > 200000 or depth > 5:
        return {"invalid": "oversized answer"}
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        return value if value.bit_length() <= 64 else {"invalid": "oversized integer"}
    if type(value) is list:
        if len(value) > 20000:
            return {"invalid": "oversized list"}
        return [snapshot(item, depth+1, counter) for item in value]
    return {"invalid": "ordinary lists and integers required", "type": type(value).__name__[:80]}


class Budget:
    def __init__(self, instance, seconds, output):
        self._deadline = time.monotonic()+seconds
        self._instance = instance
        self._output = output
        self._sent = 0
        self._best = -1

    def remaining(self):
        return max(0., self._deadline-time.monotonic())

    def expired(self):
        return self.remaining() <= 0

    def offer(self, board):
        if self.expired() or self._sent >= MAX_MESSAGES:
            return False
        report = problem.check_output(self._instance, board)
        if not report["valid"] or report["value"] <= self._best or self.expired():
            return False
        self._output.write(json.dumps(dict(type="offer", answer=board))+"\n")
        self._output.flush()
        self._best = report["value"]
        self._sent += 1
        return True


def worker():
    output = os.fdopen(os.dup(sys.stdout.fileno()), "w", buffering=1)
    payload = json.loads(sys.stdin.readline())
    if sys.platform.startswith("linux"):
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    started_import = time.process_time()
    log = LimitedLog()
    try:
        # Native library output cannot corrupt the JSON protocol or fill pipes.
        with open(os.devnull, "w") as sink:
            os.dup2(sink.fileno(), 1)
            os.dup2(sink.fileno(), 2)
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            path = Path(payload["module"])
            sys.path[:] = [p for p in sys.path if p and not (Path(p)/"grade.py").is_file()]
            for name in ("grade", "references", "config", "manifest"):
                sys.modules.pop(name, None)
            sys.path.insert(0, str(path.parent))
            module = types.ModuleType("_current_pa4_submission")
            module.__file__ = str(path)
            sys.modules[module.__name__] = module
            exec(compile(path.read_bytes(), str(path), "exec", dont_inherit=True), module.__dict__)
            output.write(json.dumps(dict(type="ready", import_cpu=time.process_time()-started_import))+"\n")
            output.flush()
            if sys.stdin.readline().strip() != "start":
                return
            started = time.process_time()
            job = payload["job"]
            budget = Budget(copy.deepcopy(job), payload["seconds"], output)
            answers = snapshot(module.solve(job, budget, random.Random(payload["seed"])))
            output.write(json.dumps(dict(type="return", answer=answers,
                 cpu=time.process_time()-started, logs=log.getvalue()))+"\n")
            output.flush()
    except BaseException:
        output.write(json.dumps(dict(type="error", error=traceback.format_exc()[-6000:], logs=log.getvalue()))+"\n")
        output.flush()
    finally:
        output.close()


def stop(process):
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        # taskkill also removes descendants on Windows.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    try:
        process.wait(timeout=.10)
    except subprocess.TimeoutExpired:
        pass
    if os.name == "posix":
        try:
            # Descendants may outlive the leader or ignore SIGTERM.
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=1)
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream:
            stream.close()


def run(module, job, seconds=3., import_seconds=10., seed=0,
        worker_directory=None, identity=None):
    for limit in (seconds, import_seconds):
        if type(limit) not in (int, float) or not math.isfinite(limit) or limit <= 0:
            raise ValueError("positive finite time limits required")
    problem.validate_instance(job)
    # Solvers receive only the published schema, never case labels or targets.
    job = {k: copy.deepcopy(job[k]) for k in ("height", "width", "blocked", "weights")}
    module = str(Path(module).resolve())
    result = dict(termination="no_answer", answer=None, offers=[], cpu=None,
                  import_cpu=None, elapsed=0., search_elapsed=0., logs="", error="")
    started = time.monotonic()
    deadline = started+import_seconds
    search_started = None
    directory = Path(worker_directory) if worker_directory else Path(__file__).resolve().parent
    permissions = {} if identity is None else dict(user=identity[0], group=identity[1], extra_groups=[])
    env = {k: v for k, v in os.environ.items()
           if k in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL")}
    env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
               PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.Popen([sys.executable, str(directory / "runner.py"), "--worker"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        cwd=directory, start_new_session=(os.name == "posix"), env=env, **permissions)
    incoming = queue.Queue(maxsize=8)
    def read_output():
        try:
            while True:
                data = os.read(p.stdout.fileno(), 65536)
                incoming.put(data)
                if not data:
                    break
        except (OSError, ValueError):
            pass
    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    buffer = b""
    received = 0
    messages = 0
    try:
        p.stdin.write((json.dumps(dict(module=module, job=job, seconds=seconds, seed=seed))+"\n").encode())
        p.stdin.flush()
        while time.monotonic() < deadline:
            try:
                data = incoming.get(timeout=max(.001, deadline-time.monotonic()))
            except queue.Empty:
                break
            if not data:
                result["termination"] = "worker_exit"
                break
            received += len(data)
            if received > MAX_BYTES:
                result["termination"] = "protocol_limit"
                break
            buffer += data
            while b"\n" in buffer:
                raw, buffer = buffer.split(b"\n", 1)
                message = json.loads(raw)
                kind = message.get("type")
                if kind == "ready" and search_started is None and time.monotonic() < deadline:
                    result["import_cpu"] = message["import_cpu"]
                    search_started = time.monotonic()
                    deadline = search_started+seconds
                    p.stdin.write(b"start\n")
                    p.stdin.flush()
                elif kind == "offer" and search_started is not None and time.monotonic() < deadline:
                    messages += 1
                    if messages <= MAX_MESSAGES:
                        # Parent-side checking prevents a display fallback or
                        # a forged worker check from becoming a graded incumbent.
                        checked = problem.check_output(job, message["answer"])
                        if checked["valid"]:
                            result["offers"].append(dict(answer=message["answer"], value=checked["value"]))
                elif kind == "return" and search_started is not None and time.monotonic() < deadline:
                    result.update(answer=message["answer"], cpu=message["cpu"],
                                  logs=message.get("logs", ""), termination="returned")
                    return result
                elif kind == "error":
                    result.update(termination="error", error=message["error"], logs=message.get("logs", ""))
                    return result
        if result["termination"] == "no_answer":
            result["termination"] = "import_timeout" if search_started is None else "search_timeout"
        return result
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        result.update(termination="protocol_error", error=traceback.format_exc()[-4000:])
        return result
    finally:
        result["elapsed"] = time.monotonic()-started
        result["search_elapsed"] = 0. if search_started is None else time.monotonic()-search_started
        stop(p)


def checked_garden(job, result):
    candidates = result["offers"][:]
    report = problem.check_output(job, result["answer"])
    if report["valid"]:
        candidates.append(dict(answer=result["answer"], value=report["value"]))
    if not candidates:
        return dict(valid=False, value=None, answer=None, errors=report["errors"])
    best = max(candidates, key=lambda x:x["value"])
    return dict(valid=True, **best, errors=[])


if __name__ == "__main__" and "--worker" in sys.argv:
    worker()
