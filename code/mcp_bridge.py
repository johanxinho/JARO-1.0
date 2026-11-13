import subprocess, json, gc
from pathlib import Path

MCP_CONFIG_FILE = Path.home() / "JohanAI/mcp_config.json"

def call_mcp_tool(server_name, tool_name, arguments):
    if not MCP_CONFIG_FILE.exists(): return "Error: No existe mcp_config.json"
    config = json.loads(MCP_CONFIG_FILE.read_text(encoding="utf-8"))
    srv = config.get("mcpServers", {}).get(server_name)
    if not srv: return f"Error: Servidor MCP {server_name} no configurado."
    cmd = [srv["command"]] + srv.get("args", [])
    proc = None
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def send_rpc(p):
            proc.stdin.write(json.dumps(p) + "\n")
            proc.stdin.flush()
            return json.loads(proc.stdout.readline())
        send_rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "jaro", "version": "2.0"}}})
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()
        res = send_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}})
        return json.dumps(res.get("result", res), ensure_ascii=False)
    except Exception as e:
        return f"Error MCP: {e}"
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=2)
        gc.collect()
