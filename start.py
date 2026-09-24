#!/usr/bin/env python3
"""
Single-command launcher for Agentic SalesMan.

Starts both the FastAPI backend and Vite frontend dev server in one
terminal. Ctrl+C stops both.

Usage:
    python start.py              # default: backend on 8000, frontend on 5173
    python start.py --backend-only
    python start.py --frontend-only
    python start.py --port 8080  # custom backend port
"""

import argparse
import os
import platform
import signal
import subprocess
import sys
import time

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")

# Colors for terminal output
IS_WINDOWS = platform.system() == "Windows"


def color(text, code):
    if IS_WINDOWS and not os.environ.get("TERM"):
        return text
    return f"\033[{code}m{text}\033[0m"


def green(t): return color(t, "32")
def yellow(t): return color(t, "33")
def cyan(t): return color(t, "36")
def red(t): return color(t, "31")
def bold(t): return color(t, "1")


def check_prerequisites():
    """Verify required tools are available."""
    errors = []

    # Check Python dependencies
    backend_reqs = os.path.join(BACKEND_DIR, "requirements.txt")
    if not os.path.exists(backend_reqs):
        errors.append(f"Missing {backend_reqs}")

    # Check .env
    env_file = os.path.join(BACKEND_DIR, ".env")
    env_example = os.path.join(BACKEND_DIR, ".env.example")
    if not os.path.exists(env_file):
        if os.path.exists(env_example):
            print(yellow("⚠  No .env file found. Copying from .env.example ..."))
            import shutil
            shutil.copy2(env_example, env_file)
            print(yellow("   Edit backend/.env with your real credentials before using."))
        else:
            errors.append("Missing backend/.env — copy .env.example and fill in your keys.")

    # Check node_modules
    node_modules = os.path.join(FRONTEND_DIR, "node_modules")
    if not os.path.exists(node_modules):
        print(yellow("⚠  Frontend dependencies not installed. Running npm install ..."))
        result = subprocess.run(
            ["npm", "install"],
            cwd=FRONTEND_DIR,
            shell=IS_WINDOWS,
        )
        if result.returncode != 0:
            errors.append("npm install failed — check your Node.js installation.")

    if errors:
        print(red("\n✖ Prerequisites not met:"))
        for e in errors:
            print(red(f"  • {e}"))
        sys.exit(1)


def start_backend(port=8000):
    """Start the FastAPI backend with uvicorn."""
    print(f"{cyan('▶ Backend')}  → http://localhost:{port}")
    print(f"           → http://localhost:{port}/docs (Swagger UI)")

    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", str(port),
        "--reload",
    ]
    return subprocess.Popen(
        cmd,
        cwd=BACKEND_DIR,
        env={**os.environ, "PYTHONPATH": BACKEND_DIR},
    )


def start_website(port=3000):
    """Serve the static product website on a local dev server."""
    website_dir = os.path.join(ROOT_DIR, "website")
    if not os.path.isfile(os.path.join(website_dir, "index.html")):
        return None
    print(f"{cyan('▶ Website')}  → http://localhost:{port}")
    cmd = [sys.executable, "-m", "http.server", str(port), "--bind", "0.0.0.0"]
    return subprocess.Popen(cmd, cwd=website_dir)


def start_frontend(backend_port=8000):
    """Start the Vite dev server."""
    print(f"{cyan('▶ Frontend')} → http://localhost:5173")

    cmd = ["npm", "run", "dev"]
    env = {**os.environ}
    # Point the Vite dev proxy (vite.config.js) at the backend's port, so
    # the browser keeps calling same-origin /api and CORS never applies.
    env["API_PROXY_TARGET"] = f"http://127.0.0.1:{backend_port}"

    return subprocess.Popen(
        cmd,
        cwd=FRONTEND_DIR,
        shell=IS_WINDOWS,
        env=env,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Start the Agentic SalesMan development servers",
    )
    parser.add_argument("--port", type=int, default=8000, help="Backend port (default: 8000)")
    parser.add_argument("--backend-only", action="store_true", help="Start backend only")
    parser.add_argument("--frontend-only", action="store_true", help="Start frontend only")
    parser.add_argument("--skip-checks", action="store_true", help="Skip prerequisite checks")
    args = parser.parse_args()

    print()
    print(bold("🛒 Agentic SalesMan — Development Server"))
    print("─" * 44)

    if not args.skip_checks:
        check_prerequisites()

    processes = []

    try:
        if not args.frontend_only:
            processes.append(("backend", start_backend(args.port)))
        if not args.backend_only:
            time.sleep(1)  # Let backend start binding first
            processes.append(("frontend", start_frontend(args.port)))

        website_proc = start_website()
        if website_proc:
            processes.append(("website", website_proc))

        print()
        print(green("✔ All servers running. Press Ctrl+C to stop."))
        print()

        # Wait for any process to exit
        while True:
            for name, proc in processes:
                ret = proc.poll()
                if ret is not None:
                    print(red(f"\n✖ {name} exited with code {ret}"))
                    raise KeyboardInterrupt
            time.sleep(1)

    except KeyboardInterrupt:
        print(yellow("\n\n⏹  Shutting down ..."))
        for name, proc in processes:
            if proc.poll() is None:
                if IS_WINDOWS:
                    proc.terminate()
                else:
                    os.kill(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                print(f"   Stopped {name}")
        print(green("   Done.\n"))


if __name__ == "__main__":
    main()
