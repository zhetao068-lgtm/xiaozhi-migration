"""小智学习工具，使用 MCP 标准输入输出和本地 SQLite。"""

import ast
import asyncio
import json
import math
import operator
import os
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode
from urllib.request import urlopen

from mcp.server.fastmcp import FastMCP
from pydantic import Field

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("XIAOZHI_STUDY_DB", HERE / "学习数据.sqlite3"))
CHINA = timezone(timedelta(hours=8))
mcp = FastMCP("小智随身学习")
OPERATIONS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
              ast.Div: operator.truediv, ast.Pow: operator.pow}


def database():
    db = sqlite3.connect(DATA)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS notes (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS timer (id INTEGER PRIMARY KEY CHECK(id = 1),
            end_at REAL NOT NULL);
    """)
    return db


def arithmetic(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        result = node.value
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = arithmetic(node.operand)
        result = -value if isinstance(node.op, ast.USub) else value
    elif isinstance(node, ast.BinOp) and type(node.op) in OPERATIONS:
        left, right = arithmetic(node.left), arithmetic(node.right)
        if isinstance(node.op, ast.Pow) and (int(right) != right or abs(right) > 12):
            raise ValueError("指数只支持 -12 到 12 的整数")
        result = OPERATIONS[type(node.op)](left, right)
    else:
        raise ValueError("只支持四则运算和整数次幂")
    if abs(result) > 10**18:
        raise ValueError("数值超出范围")
    return result


@mcp.tool()
def study_calculate(expression: str) -> str:
    """用计算器算四则运算、小数、括号和幂。参数示例 (12 * 18) / 3。"""
    expression = expression.translate(str.maketrans({"×": "*", "÷": "/", "−": "-"}))
    expression = expression.replace("^", "**").strip()
    if len(expression) > 100 or not re.fullmatch(r"[0-9+*/(). \t-]+", expression):
        raise ValueError("请输入 100 字符以内的算式")
    try:
        result = arithmetic(ast.parse(expression, mode="eval").body)
    except (SyntaxError, ArithmeticError) as error:
        raise ValueError("算式格式有误、除数为零或结果超出范围") from error
    return format(result, ".12g") if isinstance(result, float) else str(result)


@mcp.tool()
def study_china_time() -> str:
    """查询电脑时钟的北京时间，返回当前日期和时分秒。"""
    return datetime.now(CHINA).strftime("%Y-%m-%d %H:%M:%S 北京时间")


def get_json(url, **parameters):
    with urlopen(f"{url}?{urlencode(parameters)}", timeout=4) as response:
        return json.load(response)


@mcp.tool()
async def study_city_weather(city: Annotated[str, Field(min_length=2, max_length=35)]) -> str:
    """通过 Open-Meteo 联网查中国大陆城市当前气温、体感和风速。只传城市名，可加省名区分同名城市。"""
    city = city.strip()
    if len(city) < 2:
        return "请输入要查询的城市名"
    try:
        locations = await asyncio.to_thread(
            get_json, "https://geocoding-api.open-meteo.com/v1/search",
            name=city.replace("，", ","), count=1, language="zh", countryCode="CN",
        )
        matches = locations.get("results", [])
        if not matches:
            return "没有查到这个城市，请换个写法，例如北京"
        match = matches[0]
        forecast = await asyncio.to_thread(
            get_json, "https://api.open-meteo.com/v1/forecast",
            latitude=match["latitude"], longitude=match["longitude"], timezone="Asia/Shanghai",
            current="temperature_2m,apparent_temperature,wind_speed_10m",
        )
        values = forecast["current"]
        location = " ".join(dict.fromkeys(filter(None, (match.get("admin1"), match["name"]))))
        return (
            f"{location} {values['time'].replace('T', ' ')}（北京时间），"
            f"气温 {values['temperature_2m']} ℃，体感 {values['apparent_temperature']} ℃，"
            f"风速 {values['wind_speed_10m']} 公里/小时。数据来自 Open-Meteo。"
        )
    except (OSError, ValueError, KeyError):
        return "天气接口暂时没有返回可用数据，请稍后再查"


@mcp.tool()
def study_find_card(keyword: Annotated[str, Field(min_length=1, max_length=40)]) -> str:
    """搜索随包初三知识卡。传简短关键词，例如勾股定理、欧姆定律或验收代号。"""
    keyword = keyword.strip()
    cards = json.loads((HERE / "知识卡.json").read_text(encoding="utf-8"))
    matches = [card["内容"] for card in cards
               if keyword and any(keyword in term or term in keyword for term in card["词"])]
    return "\n".join(matches) or "这套本地知识卡没有收录该关键词"


@mcp.tool()
def study_save_note(name: Annotated[str, Field(min_length=1, max_length=30)],
                    value: Annotated[str, Field(min_length=1, max_length=160)]) -> str:
    """仅在用户明确要求时，把非隐私笔记存到电脑。相同标题覆盖旧内容。"""
    name, value = name.strip(), value.strip()
    if not name or not value:
        raise ValueError("标题和内容不能为空")
    with closing(database()) as db, db:
        db.execute("INSERT INTO notes VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",
                   (name, value))
    return f"已保存学习笔记《{name}》"


@mcp.tool()
def study_read_note(name: Annotated[str, Field(min_length=1, max_length=30)]) -> str:
    """按完整标题查询之前明确保存到电脑的学习笔记。"""
    with closing(database()) as db:
        row = db.execute("SELECT value FROM notes WHERE name = ?", (name.strip(),)).fetchone()
    return row[0] if row is not None else "没有找到同名学习笔记"


@mcp.tool()
def study_delete_note(name: Annotated[str, Field(min_length=1, max_length=30)]) -> str:
    """仅在用户明确要求删除时，按完整标题删除电脑上的学习笔记。"""
    with closing(database()) as db, db:
        note = db.execute("DELETE FROM notes WHERE name = ?", (name.strip(),))
    return f"已删除学习笔记《{name}》" if note.rowcount else "没有找到同名学习笔记"


@mcp.tool()
def study_add_task(title: Annotated[str, Field(min_length=1, max_length=80)]) -> str:
    """添加一条学习待办到电脑，返回编号。"""
    title = title.strip()
    if not title:
        raise ValueError("待办标题不能为空")
    with closing(database()) as db, db:
        task = db.execute("INSERT INTO tasks(title) VALUES (?)", (title,))
    return f"已添加待办 #{task.lastrowid} {title}"


@mcp.tool()
def study_list_tasks() -> str:
    """查看最近 10 条未完成的学习待办。"""
    with closing(database()) as db:
        tasks = db.execute("SELECT id, title FROM tasks WHERE done = 0 ORDER BY id DESC LIMIT 10")
        lines = [f"#{number} {title}" for number, title in tasks]
    return "\n".join(lines) or "没有未完成的学习待办"


@mcp.tool()
def study_complete_task(task_id: Annotated[int, Field(ge=1, le=2**63 - 1)]) -> str:
    """仅在用户明确要求时，按编号完成学习待办。"""
    with closing(database()) as db, db:
        task = db.execute("UPDATE tasks SET done = 1 WHERE id = ? AND done = 0", (task_id,))
    return f"已完成待办 #{task_id}" if task.rowcount else "找不到该编号的未完成待办"


@mcp.tool()
def study_start_timer(minutes: Annotated[int, Field(ge=1, le=180)]) -> str:
    """设置可随时查询的学习倒计时，会替换旧计时。没有到点主动播报功能。"""
    end_at = time.time() + minutes * 60
    with closing(database()) as db, db:
        db.execute("INSERT INTO timer VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET end_at=excluded.end_at",
                   (end_at,))
    return f"已设 {minutes} 分钟计时，可随时问还剩多久。到点不会主动播报。"


@mcp.tool()
def study_timer_status() -> str:
    """查询学习倒计时剩余时间。"""
    with closing(database()) as db:
        row = db.execute("SELECT end_at FROM timer WHERE id = 1").fetchone()
    if row is None:
        return "还没有设置学习计时"
    remaining = math.ceil(row[0] - time.time())
    if remaining <= 0:
        return "学习倒计时已结束"
    minutes, seconds = divmod(remaining, 60)
    return f"还剩 {minutes} 分 {seconds} 秒"


if __name__ == "__main__":
    mcp.run(transport="stdio")
