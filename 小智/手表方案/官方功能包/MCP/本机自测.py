"""用本机 WebSocket 模拟小智云端。使用临时数据库，不需接入点或设备。"""

import asyncio
import itertools
import json
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from 连接小智 import is_official_endpoint, run_session


async def check_session(calls):
    outcome = asyncio.get_running_loop().create_future()
    ids = itertools.count(1)

    async def mock_cloud(websocket):
        async def request(method, params):
            request_id = next(ids)
            await websocket.send(json.dumps({
                "jsonrpc": "2.0", "id": request_id, "method": method, "params": params,
            }, ensure_ascii=False, indent=2))
            reply = json.loads(await asyncio.wait_for(websocket.recv(), 8))
            assert reply["id"] == request_id and "error" not in reply, reply
            return reply["result"]

        try:
            version = "2024-11-05"
            hello = await request("initialize", {
                "protocolVersion": version, "capabilities": {},
                "clientInfo": {"name": "local-test", "version": "1"},
            })
            assert hello["protocolVersion"] == version
            await websocket.send('{"jsonrpc":"2.0","method":"notifications/initialized"}')
            tools = (await request("tools/list", {}))["tools"]
            assert len(tools) == 12
            for name, arguments, expected, is_error in calls:
                result = await request("tools/call", {"name": name, "arguments": arguments})
                assert bool(result.get("isError")) == is_error, result
                assert expected in result["content"][0]["text"], result
                print("通过", name, expected)
            outcome.set_result(None)
        except Exception as error:
            outcome.set_exception(error)
        finally:
            await websocket.close()

    async with serve(mock_cloud, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}") as websocket:
            await asyncio.wait_for(run_session(websocket), 20)
        await outcome


async def main():
    assert is_official_endpoint("wss://api.xiaozhi.me/mcp/?token=synthetic")
    assert not is_official_endpoint("ws://api.xiaozhi.me/mcp/?token=synthetic")
    assert not is_official_endpoint("wss://api.xiaozhi.me@elsewhere.test/mcp/?token=synthetic")
    first = [
        ("study_calculate", {"expression": "12 × 18"}, "216", False),
        ("study_calculate", {"expression": "(2+3)^2 ÷ 4"}, "6.25", False),
        ("study_calculate", {"expression": "1/0"}, "除数为零", True),
        ("study_calculate", {"expression": '__import__("os")'}, "请输入", True),
        ("study_calculate", {"expression": "2^100"}, "指数只支持", True),
        ("study_china_time", {}, "北京时间", False),
        ("study_city_weather", {"city": "  "}, "请输入", False),
        ("study_find_card", {"keyword": "验收代号"}, "青柠四十二号", False),
        ("study_find_card", {"keyword": " "}, "没有收录", False),
        ("study_read_note", {"name": "测试"}, "没有找到", False),
        ("study_save_note", {"name": "测试", "value": "紫色风车七号"}, "已保存", False),
        ("study_add_task", {"title": "练习勾股定理"}, "#1", False),
        ("study_timer_status", {}, "还没有", False),
        ("study_start_timer", {"minutes": 0}, "greater than or equal to 1", True),
        ("study_start_timer", {"minutes": 1}, "已设 1 分钟", False),
        ("study_timer_status", {}, "还剩", False),
    ]
    second = [
        ("study_read_note", {"name": "测试"}, "紫色风车七号", False),
        ("study_list_tasks", {}, "练习勾股定理", False),
        ("study_complete_task", {"task_id": 1}, "已完成", False),
        ("study_complete_task", {"task_id": 1}, "找不到", False),
        ("study_list_tasks", {}, "没有未完成", False),
        ("study_timer_status", {}, "已结束", False),
        ("study_delete_note", {"name": "测试"}, "已删除", False),
        ("study_read_note", {"name": "测试"}, "没有找到", False),
    ]
    if "--online" in sys.argv:
        second.append(("study_city_weather", {"city": "北京"}, "数据来自 Open-Meteo", False))
    with TemporaryDirectory(prefix="xiaozhi-study-test-") as directory:
        path = Path(directory) / "test.sqlite3"
        os.environ["XIAOZHI_STUDY_DB"] = str(path)
        await check_session(first)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("UPDATE timer SET end_at = 0")
        await check_session(second)
    print(f"全部通过，2 次连接、12 项工具、{len(first) + len(second)} 次调用。")


if __name__ == "__main__":
    asyncio.run(main())
