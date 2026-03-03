"""
Remarkable Bridge Server
Runs remarkable-mcp tools and exposes them via HTTP for the Vercel notes app.
Deploy to Railway — set REMARKABLE_TOKEN env var.
"""
import os
import json
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

# We'll call rm-mcp tools directly using the remarkable cloud client
# rather than spawning a subprocess for each request

REMARKABLE_TOKEN = os.environ.get("REMARKABLE_TOKEN", "")
PORT = int(os.environ.get("PORT", 8080))

async def run_tool(tool_name, params):
    """Run a remarkable-mcp tool via subprocess and return result."""
    import subprocess
    import sys
    
    # Build a small Python snippet that calls the tool
    script = f"""
import asyncio
import os
os.environ['REMARKABLE_TOKEN'] = {repr(REMARKABLE_TOKEN)}

from remarkable_mcp.server import (
    remarkable_browse, remarkable_read, 
    remarkable_search, remarkable_recent, remarkable_status
)

async def main():
    try:
        tool_fn = {{
            'remarkable_browse': remarkable_browse,
            'remarkable_read': remarkable_read,
            'remarkable_search': remarkable_search,
            'remarkable_recent': remarkable_recent,
            'remarkable_status': remarkable_status,
        }}.get({repr(tool_name)})
        
        if not tool_fn:
            print(json.dumps({{"error": "Unknown tool: " + {repr(tool_name)}}}))
            return
            
        result = await tool_fn(**{repr(params)})
        # result is a list of TextContent objects
        if hasattr(result, '__iter__'):
            texts = []
            for item in result:
                if hasattr(item, 'text'):
                    texts.append(item.text)
                else:
                    texts.append(str(item))
            print(json.dumps({{"result": chr(10).join(texts)}}))
        else:
            print(json.dumps({{"result": str(result)}}))
    except Exception as e:
        print(json.dumps({{"error": str(e)}}))

import json
asyncio.run(main())
"""
    
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    
    try:
        return json.loads(stdout.decode())
    except:
        return {"error": stderr.decode() or "Unknown error"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging
    
    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)
    
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
    
    def do_GET(self):
        if self.path == "/health":
            self.send_json({"status": "ok", "token_set": bool(REMARKABLE_TOKEN)})
        else:
            self.send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        # Validate secret token
        auth = self.headers.get("Authorization", "")
        expected = "Bearer " + os.environ.get("BRIDGE_SECRET", "")
        if os.environ.get("BRIDGE_SECRET") and auth != expected:
            self.send_json({"error": "Unauthorized"}, 401)
            return
        
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        
        try:
            req = json.loads(body)
        except:
            self.send_json({"error": "Invalid JSON"}, 400)
            return
        
        tool = req.get("tool")
        params = req.get("params", {})
        
        if not tool:
            self.send_json({"error": "Missing 'tool' field"}, 400)
            return
        
        result = asyncio.run(run_tool(tool, params))
        self.send_json(result)


if __name__ == "__main__":
    if not REMARKABLE_TOKEN:
        print("WARNING: REMARKABLE_TOKEN not set")
    
    print(f"Starting Remarkable Bridge on port {PORT}")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
