"""
Remarkable Bridge Server
Wraps rm-mcp CLI tool and exposes HTTP endpoints for Vercel notes app.
"""
import os
import json
import asyncio
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

REMARKABLE_TOKEN = os.environ.get("REMARKABLE_TOKEN", "")
BRIDGE_SECRET    = os.environ.get("BRIDGE_SECRET", "")
PORT             = int(os.environ.get("PORT", 8080))

async def run_rmmcp_tool(tool_name, params):
    """Call rm-mcp via a small Python script using the cloud API."""
    script = f"""
import asyncio, os, sys, json
os.environ["REMARKABLE_TOKEN"] = {json.dumps(REMARKABLE_TOKEN)}

try:
    from remarkable_mcp.server import create_server
    from remarkable_mcp.cloud import RemarkableCloud
except ImportError as e:
    print(json.dumps({{"error": "Import failed: " + str(e)}}))
    sys.exit(0)

async def main():
    try:
        cloud = RemarkableCloud(token={json.dumps(REMARKABLE_TOKEN)})
        await cloud.refresh_token()

        from remarkable_mcp import tools

        fn_map = {{
            "remarkable_browse":  tools.browse,
            "remarkable_read":    tools.read,
            "remarkable_search":  tools.search,
            "remarkable_recent":  tools.recent,
            "remarkable_status":  tools.status,
        }}

        fn = fn_map.get({json.dumps(tool_name)})
        if not fn:
            print(json.dumps({{"error": "Unknown tool: " + {json.dumps(tool_name)}}}))
            return

        params = {json.dumps(params)}
        result = await fn(cloud, **params)
        if isinstance(result, list):
            text = "\\n".join(getattr(r, "text", str(r)) for r in result)
        else:
            text = str(result)
        print(json.dumps({{"result": text}}))
    except Exception as e:
        print(json.dumps({{"error": str(e)}}))

asyncio.run(main())
"""
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "REMARKABLE_TOKEN": REMARKABLE_TOKEN}
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        raw = stdout.decode().strip()
        if raw:
            return json.loads(raw)
        return {"error": stderr.decode().strip() or "No output from bridge"}
    except asyncio.TimeoutError:
        return {"error": "Tool timed out after 30s"}
    except Exception as e:
        return {"error": str(e)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")

    def cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_json({
                "status": "ok",
                "token_set": bool(REMARKABLE_TOKEN),
                "python": sys.version
            })
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        # Auth check
        if BRIDGE_SECRET:
            auth = self.headers.get("Authorization", "")
            if auth != "Bearer " + BRIDGE_SECRET:
                self.send_json({"error": "Unauthorized"}, 401)
                return

        length = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(length))
        except Exception:
            self.send_json({"error": "Invalid JSON"}, 400)
            return

        tool   = req.get("tool", "").strip()
        params = req.get("params", {})

        if not tool:
            self.send_json({"error": "Missing 'tool' field"}, 400)
            return

        print(f"Calling tool: {tool} params: {params}")
        result = asyncio.run(run_rmmcp_tool(tool, params))
        print(f"Result: {str(result)[:200]}")
        self.send_json(result)


if __name__ == "__main__":
    # Install rm-mcp if not present
    try:
        import remarkable_mcp
        print("remarkable_mcp already installed")
    except ImportError:
        print("Installing rm-mcp...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "rm-mcp"])
        print("rm-mcp installed")

    if not REMARKABLE_TOKEN:
        print("WARNING: REMARKABLE_TOKEN not set!")
    else:
        print(f"Token set: {REMARKABLE_TOKEN[:30]}...")

    print(f"Starting bridge on port {PORT}")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
