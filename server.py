"""
Remarkable Bridge Server - calls rm-mcp directly in-process
"""
import os, json, asyncio, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

REMARKABLE_TOKEN = os.environ.get("REMARKABLE_TOKEN", "")
BRIDGE_SECRET    = os.environ.get("BRIDGE_SECRET", "")
PORT             = int(os.environ.get("PORT", 8080))

# Set token env var before importing rm-mcp
os.environ["REMARKABLE_TOKEN"] = REMARKABLE_TOKEN

# Import rm-mcp tools directly
try:
    from remarkable_mcp.server import (
        remarkable_browse,
        remarkable_read,
        remarkable_search,
        remarkable_recent,
        remarkable_status,
    )
    TOOLS = {
        "remarkable_browse":  remarkable_browse,
        "remarkable_read":    remarkable_read,
        "remarkable_search":  remarkable_search,
        "remarkable_recent":  remarkable_recent,
        "remarkable_status":  remarkable_status,
    }
    print("rm-mcp tools loaded successfully")
except Exception as e:
    print(f"Failed to import rm-mcp: {e}")
    TOOLS = {}


def run_tool(tool_name, params):
    """Run a tool synchronously."""
    if not TOOLS:
        return {"error": "rm-mcp not loaded"}
    
    fn = TOOLS.get(tool_name)
    if not fn:
        return {"error": f"Unknown tool: {tool_name}"}
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(fn(**params))
        loop.close()
        
        # Extract text from MCP content objects
        if isinstance(result, list):
            texts = []
            for item in result:
                if hasattr(item, "text"):
                    texts.append(item.text)
                elif hasattr(item, "content"):
                    for c in item.content:
                        if hasattr(c, "text"):
                            texts.append(c.text)
                else:
                    texts.append(str(item))
            return {"result": "\n".join(texts)}
        else:
            return {"result": str(result)}
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
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_json({
                "status": "ok",
                "token_set": bool(REMARKABLE_TOKEN),
                "tools_loaded": bool(TOOLS),
                "python": sys.version
            })
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
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
            self.send_json({"error": "Missing tool"}, 400)
            return

        print(f"Tool: {tool} params: {params}")
        result = run_tool(tool, params)
        print(f"Result: {str(result)[:300]}")
        self.send_json(result)


if __name__ == "__main__":
    if not REMARKABLE_TOKEN:
        print("WARNING: REMARKABLE_TOKEN not set!")
    if not TOOLS:
        print("WARNING: No tools loaded — check rm-mcp install")
    print(f"Starting bridge on port {PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
