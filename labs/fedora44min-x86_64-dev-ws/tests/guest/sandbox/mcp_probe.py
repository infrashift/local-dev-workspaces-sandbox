"""A minimal MCP client the sandbox suite runs ON the guest, with the standard library only.

    mcp_probe.py stdio <tool> <arguments-json> <command> [<arg>...]
    mcp_probe.py http <tool> <arguments-json> <url> [<header>=<value>...]

It initialises a session, calls one tool and prints one JSON object:
{"server": <serverInfo>, "result": <the tools/call result>} on success, or
{"status": <HTTP status>, "body": ...} / {"error": ...} when the server
refuses. stdio servers inherit this process's environment; http requests go
wherever urllib's proxy settings (HTTPS_PROXY, NO_PROXY) send them.
"""

import json
import subprocess
import sys
import urllib.error
import urllib.request

PROTOCOL = "2025-11-25"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": PROTOCOL,
        "capabilities": {},
        "clientInfo": {"name": "ai-sandbox-verify", "version": "1"},
    },
}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}


def tool_call(tool, arguments):
    return {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool, "arguments": arguments}}


def outcome(init, reply):
    if "error" in init:
        return {"error": init["error"]}
    info = init["result"].get("serverInfo", {})
    server = {"name": info.get("name"), "version": info.get("version")}
    if "error" in reply:
        return {"server": server, "error": reply["error"]}
    return {"server": server, "result": reply["result"]}


def stdio(tool, arguments, argv):
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def send(message):
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def receive(message_id):
        for line in proc.stdout:
            message = json.loads(line)
            if message.get("id") == message_id:
                return message
        raise SystemExit(json.dumps({"error": f"the server exited with {proc.wait()}"}))

    try:
        send(INITIALIZE)
        init = receive(1)
        send(INITIALIZED)
        send(tool_call(tool, arguments))
        return outcome(init, receive(2))
    finally:
        proc.stdin.close()
        proc.terminate()
        proc.wait(10)


def sse_message(body, message_id):
    """The JSON-RPC message with this id in a text/event-stream body."""
    for line in body.splitlines():
        if line.startswith("data:"):
            message = json.loads(line[5:].strip())
            if message.get("id") == message_id:
                return message
    raise ValueError("no reply in the event stream")


def http(tool, arguments, url, headers):
    session = {}

    def post(message):
        request_headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        request_headers.update(headers)
        if session:
            request_headers.update({"Mcp-Session-Id": session["id"], "MCP-Protocol-Version": PROTOCOL})
        request = urllib.request.Request(url, json.dumps(message).encode(), request_headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, response.headers, response.read().decode()
        except urllib.error.HTTPError as err:
            return err.code, err.headers, err.read().decode()

    def reply(status, response_headers, body, message_id):
        if "text/event-stream" in response_headers.get("Content-Type", ""):
            return sse_message(body, message_id)
        return json.loads(body)

    status, response_headers, body = post(INITIALIZE)
    if status != 200:
        return {"status": status, "body": body[:500]}
    init = reply(status, response_headers, body, 1)
    if response_headers.get("Mcp-Session-Id"):
        session["id"] = response_headers["Mcp-Session-Id"]
    post(INITIALIZED)
    status, response_headers, body = post(tool_call(tool, arguments))
    if status != 200:
        return {"status": status, "body": body[:500]}
    return outcome(init, reply(status, response_headers, body, 2))


def main(argv):
    transport, tool, arguments, target, *rest = argv
    if transport == "stdio":
        result = stdio(tool, json.loads(arguments), [target, *rest])
    else:
        result = http(tool, json.loads(arguments), target, dict(item.split("=", 1) for item in rest))
    print(json.dumps(result))


if __name__ == "__main__":
    main(sys.argv[1:])
