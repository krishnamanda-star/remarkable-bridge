"""
Remarkable Bridge Server
Uses rm_mcp tools directly (correct module name: rm_mcp not remarkable_mcp)
"""
import os, json, asyncio, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

REMARKABLE_TOKEN = os.environ.get("REMARKABLE_TOKEN", "")
BRIDGE_SECRET    = os.environ.get("BRIDGE_SECRET", "")
PORT             = int(os.environ.get("PORT", 8080))

os.environ["REMARKABLE_TOKEN"] = REMARKABLE_TOKEN

try:
    from rm_mcp.tools.browse import remarkable_browse
    from rm_mcp.tools.read   import remarkable_read
    from rm_mcp.tools.search import remarkable_search
    from rm_mcp.tools.recent import remarkable_recent
    from rm_mcp.tools.status import remarkable_status

    TOOLS = {
        "remarkable_browse": (remarkable_browse, False),
        "remarkable_read":   (remarkable_read,   True),   # async
        "remarkable_search": (remarkable_search, False),
        "remarkable_recent": (remarkable_recent, False),
        "remarkable_status": (remarkable_status, False),
    }
    print("rm_mcp tools loaded OK")
except Exception as e:
    print(f"Failed to load rm_mcp: {e}")
    TOOLS = {}


def run_tool(tool_name, params):
    if not TOOLS:
        return {"error": "rm_mcp not loaded"}

    entry = TOOLS.get(tool_name)
    if not entry:
        return {"error": f"Unknown tool: {tool_name}"}

    fn, is_async = entry

    # Filter params to only those the function accepts
    import inspect
    sig = inspect.signature(fn)
    valid = {k: v for k, v in params.items() if k in sig.parameters}

    try:
        if is_async:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(fn(**valid))
            loop.close()
        else:
            result = fn(**valid)
        return {"result": str(result) if result is not None else "No results"}
    except Exception as e:
        return {"error": str(e)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204); self.cors(); self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_json({
                "status": "ok",
                "token_set": bool(REMARKABLE_TOKEN),
                "tools_loaded": list(TOOLS.keys()),
                "python": sys.version
            })
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if BRIDGE_SECRET:
            if self.headers.get("Authorization","") != "Bearer " + BRIDGE_SECRET:
                self.send_json({"error": "Unauthorized"}, 401); return

        length = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(length))
        except:
            self.send_json({"error": "Invalid JSON"}, 400); return

        tool   = req.get("tool", "").strip()
        params = req.get("params", {})
        if not tool:
            self.send_json({"error": "Missing tool"}, 400); return

        print(f"Tool: {tool} params: {params}")
        result = run_tool(tool, params)
        print(f"Result: {str(result)[:300]}")
        self.send_json(result)


if __name__ == "__main__":
    if not REMARKABLE_TOKEN:
        print("WARNING: REMARKABLE_TOKEN not set!")
    print(f"Starting bridge on port {PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
