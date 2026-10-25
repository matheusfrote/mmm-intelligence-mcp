"""Bound worker process trees; no changes to global host CPU or power settings."""

import os
import signal
import subprocess


def run_worker(args, *, timeout, env, cwd, stdout):
    """Kill the whole spawned tree on timeout and enforce Windows CPU/memory job limits."""
    cpu = int(os.environ.get("MMM_WORKER_CPU_PERCENT", "50"))
    memory = int(os.environ.get("MMM_WORKER_MEMORY_MB", "4096"))
    if not 1 <= cpu <= 100 or not 512 <= memory <= 32768:
        raise ValueError("Invalid worker CPU percentage or memory limit")
    job = None
    process = subprocess.Popen(
        args,
        cwd=cwd,
        env=env,
        stdout=stdout,
        stderr=stdout,
        stdin=subprocess.DEVNULL,
        start_new_session=os.name != "nt",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            import win32api
            import win32con
            import win32job

            job = win32job.CreateJobObject(None, "")
            info = win32job.QueryInformationJobObject(
                job, win32job.JobObjectExtendedLimitInformation
            )
            info["BasicLimitInformation"]["LimitFlags"] = (
                win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | win32job.JOB_OBJECT_LIMIT_JOB_MEMORY
            )
            info["JobMemoryLimit"] = memory * 1024 * 1024
            win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)

            class CpuRate(ctypes.Structure):
                _fields_ = [("ControlFlags", wintypes.DWORD), ("CpuRate", wintypes.DWORD)]

            rate = CpuRate(0x1 | 0x4, cpu * 100)
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.SetInformationJobObject.argtypes = [
                wintypes.HANDLE,
                ctypes.c_int,
                ctypes.c_void_p,
                wintypes.DWORD,
            ]
            kernel.SetInformationJobObject.restype = wintypes.BOOL
            if not kernel.SetInformationJobObject(
                int(job), 15, ctypes.byref(rate), ctypes.sizeof(rate)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            handle = win32api.OpenProcess(
                win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE, False, process.pid
            )
            try:
                win32job.AssignProcessToJobObject(job, handle)
            finally:
                handle.Close()
        code = process.wait(timeout=timeout)
        return subprocess.CompletedProcess(args, code)
    finally:
        if job is not None:
            job.Close()  # Includes R/Python descendants, even if the immediate child has exited.
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()
        process.wait()
