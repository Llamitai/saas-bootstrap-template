#!/usr/bin/env python3
"""
Start one or more servers, wait for them to be ready, run a command, then clean up.

Usage:
    # Single server
    python scripts/with_server.py --server "npm run dev" --port 5173 -- python automation.py
    python scripts/with_server.py --server "npm start" --port 3000 -- python test.py

    # Multiple servers
    python scripts/with_server.py \
      --server "cd backend && python server.py" --port 3000 \
      --server "cd frontend && npm run dev" --port 5173 \
      -- python test.py

Each port must be free before its server starts; an already-listening port is an
error because an unidentified server must never be reused. Server output goes to
/dev/null unless --log is given. Every server runs in its own process group, so
cleanup also stops the children spawned by the shell command.
"""

import argparse
import os
import signal
import socket
import subprocess
import sys
import time


def error(message):
    print(f"Error: {message}", file=sys.stderr)


def is_port_in_use(port):
    """Return True if something already accepts connections on the port."""
    try:
        with socket.create_connection(('localhost', port), timeout=1):
            return True
    except OSError:
        return False


def group_alive(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def stop_server(process, grace=5):
    """SIGTERM the server's process group, then SIGKILL whatever survives."""
    pgid = process.pid
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.time() + grace
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass
    while group_alive(pgid) and time.time() < deadline:
        time.sleep(0.1)
    if group_alive(pgid):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def is_server_ready(port, timeout=30, process=None):
    """Wait for server to be ready by polling the port."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if process is not None and process.poll() is not None:
            return False
        try:
            with socket.create_connection(('localhost', port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def main():
    parser = argparse.ArgumentParser(description='Run command with one or more servers')
    parser.add_argument('--server', action='append', dest='servers', required=True, help='Server command (can be repeated)')
    parser.add_argument('--port', action='append', dest='ports', type=int, required=True, help='Port for each server (must match --server count)')
    parser.add_argument('--timeout', type=int, default=30, help='Timeout in seconds per server (default: 30)')
    parser.add_argument('--log', help='Append server stdout/stderr to this file (default: discard)')
    parser.add_argument('command', nargs=argparse.REMAINDER, help='Command to run after server(s) ready')

    args = parser.parse_args()

    # Remove the '--' separator if present
    if args.command and args.command[0] == '--':
        args.command = args.command[1:]

    if not args.command:
        error("No command specified to run")
        sys.exit(1)

    # Parse server configurations
    if len(args.servers) != len(args.ports):
        error("Number of --server and --port arguments must match")
        sys.exit(1)

    busy = [port for port in args.ports if is_port_in_use(port)]
    if busy:
        error(
            f"Port(s) already in use: {', '.join(map(str, busy))}. "
            "Refusing to reuse an unidentified server; stop it or choose a free port."
        )
        sys.exit(1)

    servers = []
    for cmd, port in zip(args.servers, args.ports):
        servers.append({'cmd': cmd, 'port': port})

    server_processes = []
    log_file = open(args.log, 'ab') if args.log else None
    output = log_file if log_file else subprocess.DEVNULL

    try:
        # Start all servers
        for i, server in enumerate(servers):
            print(f"Starting server {i+1}/{len(servers)}: {server['cmd']}")

            # Use shell=True to support commands with cd and &&; a new session
            # gives the shell and its children one process group to stop.
            process = subprocess.Popen(
                server['cmd'],
                shell=True,
                stdout=output,
                stderr=subprocess.STDOUT if log_file else subprocess.DEVNULL,
                start_new_session=True,
            )
            server_processes.append(process)

            # Wait for this server to be ready
            print(f"Waiting for server on port {server['port']}...")
            if not is_server_ready(server['port'], timeout=args.timeout, process=process):
                if process.poll() is not None:
                    error(f"Server exited with code {process.returncode} before listening on port {server['port']}")
                else:
                    error(f"Server failed to start on port {server['port']} within {args.timeout}s")
                sys.exit(1)

            print(f"Server ready on port {server['port']}")

        print(f"\nAll {len(servers)} server(s) ready")

        # Run the command
        print(f"Running: {' '.join(args.command)}\n")
        result = subprocess.run(args.command)
        sys.exit(result.returncode)

    finally:
        # Clean up all servers
        print(f"\nStopping {len(server_processes)} server(s)...")
        for i, process in enumerate(server_processes):
            stop_server(process)
            print(f"Server {i+1} stopped")
        if log_file:
            log_file.close()
        print("All servers stopped")


if __name__ == '__main__':
    main()