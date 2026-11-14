"""按小智官方示例的传输方式，在 WSS 和本地 MCP stdio 之间转发消息。"""

import asyncio
import getpass
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus, WebSocketException

SERVER = Path(__file__).resolve().with_name("学习工具.py")


def is_official_endpoint(endpoint):
    try:
        url = urlsplit(endpoint)
        token = parse_qs(url.query).get("token", [])
        return (url.scheme == "wss" and url.netloc in ("api.xiaozhi.me", "api.xiaozhi.me:443")
                and url.path in ("/mcp", "/mcp/") and not url.fragment and len(token) == 1)
    except ValueError:
        return False


async def send_to_server(websocket, stdin):
    async for message in websocket:
        # stdio MCP requires exactly one JSON message per line.
        payload = json.dumps(json.loads(message), separators=(",", ":"), ensure_ascii=False)
        stdin.write(payload.encode("utf-8") + b"\n")
        await stdin.drain()


async def send_to_cloud(stdout, websocket):
    while line := await stdout.readline():
        await websocket.send(line.decode("utf-8").strip())


async def run_session(websocket):
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-u", str(SERVER), stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )
    tasks = [
        asyncio.create_task(send_to_server(websocket, process.stdin)),
        asyncio.create_task(send_to_cloud(process.stdout, websocket)),
    ]
    try:
        finished, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in finished:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
        await process.wait()


async def connect_forever(endpoint):
    delay = 2
    while True:
        try:
            async with connect(endpoint, open_timeout=10, max_size=256 * 1024) as websocket:
                print("已连接小智。回设备说“用学习工具算 12 乘 18”。Ctrl+C 退出。")
                delay = 2
                await run_session(websocket)
        except InvalidStatus as error:
            status = error.response.status_code
            print(f"接入点返回 HTTP {status}。")
            if status in (400, 401, 403, 404):
                return 1
        except (OSError, ValueError, TimeoutError, WebSocketException) as error:
            print(f"连接中断（{type(error).__name__}）。")
        print(f"{delay} 秒后重连。")
        await asyncio.sleep(delay)
        delay = min(delay * 2, 30)


def main():
    try:
        endpoint = getpass.getpass("粘贴小智官方 MCP 接入点并回车（输入不会显示） ").strip()
        if not is_official_endpoint(endpoint):
            print("请在小智官网复制完整的官方 MCP 接入点。")
            return 1
        return asyncio.run(connect_forever(endpoint))
    except (KeyboardInterrupt, EOFError):
        print("\n学习工具已停止。")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
