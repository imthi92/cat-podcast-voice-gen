#!/usr/bin/env python3
"""
Deepnote Webhook Server
Listens for GitHub Actions triggers and runs the podcast pipeline.
Run this on Deepnote: python automation/webhook_server.py

GitHub Actions sends a POST to http://<deepnote-ip>:5000/trigger
"""

import os
import sys
import json
import subprocess
import threading
import hashlib
import hmac
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

PORT = 5000
SECRET = os.environ.get("WEBHOOK_SECRET", "cat-podcast-trigger-2026")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webhook_log.txt")

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def run_pipeline():
    """Run the full podcast pipeline in background."""
    log("Starting pipeline...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(script_dir)

    try:
        # Git pull latest
        log("Pulling latest code...")
        subprocess.run(["git", "pull"], cwd=repo_dir, capture_output=True, timeout=30)

        # Run generator
        log("Running episode generator...")
        result = subprocess.run(
            [sys.executable, os.path.join(script_dir, "generate_episode.py")],
            cwd=script_dir,
            capture_output=True,
            text=True,
            timeout=1800  # 30 min timeout
        )

        if result.returncode == 0:
            log("Pipeline completed successfully!")
            log(f"Output: {result.stdout[-500:]}")
        else:
            log(f"Pipeline failed with code {result.returncode}")
            log(f"Error: {result.stderr[-500:]}")

    except subprocess.TimeoutExpired:
        log("Pipeline timed out after 30 minutes")
    except Exception as e:
        log(f"Pipeline error: {e}")


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Verify path
        if self.path != "/trigger":
            self.send_response(404)
            self.end_headers()
            return

        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        # Verify secret
        provided_secret = self.headers.get("X-Webhook-Secret", "")
        if provided_secret != SECRET:
            log(f"Unauthorized trigger attempt from {self.client_address[0]}")
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"Unauthorized")
            return

        # Start pipeline in background thread
        log(f"Trigger received from {self.client_address[0]}")
        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Pipeline started")

    def do_GET(self):
        if self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            status = {
                "status": "running",
                "server": "cat-podcast-webhook",
                "timestamp": datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(status).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        log(f"HTTP: {format % args}")


if __name__ == "__main__":
    log(f"Starting webhook server on port {PORT}...")
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    log(f"Server listening on http://0.0.0.0:{PORT}")
    log("Endpoints:")
    log(f"  POST http://<ip>:{PORT}/trigger  — Start pipeline")
    log(f"  GET  http://<ip>:{PORT}/status   — Check status")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Server stopped.")
        server.server_close()
