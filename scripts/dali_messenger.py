#!/usr/bin/env python3
"""
Dali-c_lawd Inter-Agent Messenger
Simple HTTP server for real-time messaging between OpenClaw instances over Tailscale.
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import threading

PORT = 8766
INBOX_FILE = os.path.expanduser("~/inbox.jsonl")
OUTBOX_FILE = os.path.expanduser("~/outbox.jsonl")

class MessengerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/message":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            
            try:
                msg = json.loads(body)
                msg["received_at"] = datetime.now().isoformat()
                
                # Append to inbox
                with open(INBOX_FILE, "a") as f:
                    f.write(json.dumps(msg) + "\n")
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
                
                print(f"📨 Received: {msg.get('from', 'unknown')} - {msg.get('text', '')[:50]}...")
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "invalid json"}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        if self.path == "/inbox":
            # Return unread messages and mark as read
            messages = []
            if os.path.exists(INBOX_FILE):
                with open(INBOX_FILE, "r") as f:
                    for line in f:
                        if line.strip():
                            messages.append(json.loads(line))
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(messages).encode())
            
            # Clear inbox after reading (simple approach)
            open(INBOX_FILE, "w").close()
        elif self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

def send_message(target_ip, text, sender="dali"):
    """Send a message to the other agent."""
    import urllib.request
    
    msg = {
        "from": sender,
        "text": text,
        "sent_at": datetime.now().isoformat()
    }
    
    try:
        req = urllib.request.Request(
            f"http://{target_ip}:{PORT}/message",
            data=json.dumps(msg).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode()
    except Exception as e:
        return f"Error: {e}"

def start_server():
    server = HTTPServer(("0.0.0.0", PORT), MessengerHandler)
    print(f"🚀 Messenger running on port {PORT}")
    server.serve_forever()

if __name__ == "__main__":
    # If run with arguments, send a message and exit
    import sys
    if len(sys.argv) > 2:
        target = sys.argv[1]
        text = " ".join(sys.argv[2:])
        print(send_message(target, text))
    else:
        start_server()
