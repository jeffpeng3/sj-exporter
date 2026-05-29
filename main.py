import asyncio
import os
import aiohttp
from dotenv import load_dotenv
from aiohttp import web
from prometheus_client import Gauge
from prometheus_client.aiohttp import make_aiohttp_handler
from shioaji import FuturePosition, StockPosition
from datetime import datetime, date, timedelta, time
from zoneinfo import ZoneInfo
from list_holdings import HoldingsClient
from work import is_scheduled_trading_day, is_typhoon_closed_today
load_dotenv()
tz = ZoneInfo("Asia/Taipei")

POSITION_PRICE = Gauge(
    "shioaji_position_price",
    "Stock position average price",
    ["code"],
)
POSITION_PNL = Gauge(
    "shioaji_position_pnl",
    "Stock position profit and loss",
    ["code"],
)
POSITION_ROI = Gauge(
    "shioaji_position_roi",
    "Stock position return on investment percentage",
    ["code"],
)
OVERALL_ROI = Gauge(
    "shioaji_overall_roi",
    "Overall portfolio return on investment percentage",
)

app = web.Application()
app.router.add_get("/metrics", make_aiohttp_handler())

LAST_POSITION_LABELS: set[str] = set()
EXPORT_INTERVAL_SECONDS = 60

START_TRADE_TIME = time(8, 50)
END_TRADE_TIME = time(13, 40)

CURRENT_DATE = date(1970, 1, 1)
IS_TRADING_DAY = False
IS_TRADING_TIME = False

def set_position_metrics(position: StockPosition | FuturePosition) -> None:
    code = position.code
    POSITION_PRICE.labels(code).set(position.price)
    POSITION_PNL.labels(code).set(position.pnl)
    cost = position.price * position.quantity
    roi = position.pnl / cost * 100 if cost else 0.0
    POSITION_ROI.labels(code).set(roi)


def remove_position_metrics(code: str) -> None:
    POSITION_PRICE.remove(code)
    POSITION_PNL.remove(code)
    POSITION_ROI.remove(code)

async def update_trading_day(client: HoldingsClient) -> bool:
    global CURRENT_DATE
    global IS_TRADING_DAY
    now = datetime.now(tz=tz)
    today = now.date()
    if today != CURRENT_DATE:
        CURRENT_DATE = today
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            IS_TRADING_DAY = is_scheduled_trading_day() and not await is_typhoon_closed_today(session)
        if IS_TRADING_DAY:
            await client.refresh_token()

    return IS_TRADING_DAY

async def update_trading_time() -> bool:
    global IS_TRADING_TIME
    now = datetime.now(tz=tz)
    current_time = now.time()
    IS_TRADING_TIME = START_TRADE_TIME <= current_time <= END_TRADE_TIME
    return IS_TRADING_TIME

async def sleep_until_next_trading_time() -> None:
    now = datetime.now(tz=tz)
    if now.time() < START_TRADE_TIME:
        target_time = datetime.combine(now.date(), START_TRADE_TIME, tzinfo=tz)
    elif not IS_TRADING_TIME or now.time() > END_TRADE_TIME:
        target_time = datetime.combine(now.date() + timedelta(days=1), START_TRADE_TIME, tzinfo=tz)
    else:
        return
    total_seconds = (target_time - now).total_seconds()
    print(f"尚未在交易時間內，等待直到 {target_time.strftime('%Y-%m-%d %H:%M:%S')}，正在等待 {total_seconds:.0f} 秒...")
    await asyncio.sleep(total_seconds)


async def collect_position_metrics(client: HoldingsClient, init: bool = False) -> None:
    if not init:
        if not await update_trading_day(client):
            print("今天不是交易日，等待直到下一個交易日...")
            await sleep_until_next_trading_time()
            return

        if not await update_trading_time():
            print("尚未在交易時間內，等待直到下一個交易時間...")
            await sleep_until_next_trading_time()
            return


    await client.ensure_logged_in()
    positions = await client.list_positions()
    current_labels: set[str] = set()

    total_cost = 0.0
    total_pnl = 0.0

    for position in positions.values():
        code = str(getattr(position, "code", ""))
        if not code:
            continue
        current_labels.add(code)
        set_position_metrics(position)
        total_cost += position.price * position.quantity
        total_pnl += position.pnl

    overall_roi = (total_pnl / total_cost * 100) if total_cost else 0.0
    OVERALL_ROI.set(overall_roi)

    stale_labels = LAST_POSITION_LABELS - current_labels
    for code in stale_labels:
        remove_position_metrics(code)

    LAST_POSITION_LABELS.clear()
    LAST_POSITION_LABELS.update(current_labels)


async def update_metrics(app):
    client = HoldingsClient()
    await collect_position_metrics(client, init=True)
    while True:
        for i in range(10):
            await asyncio.sleep(EXPORT_INTERVAL_SECONDS)
            try:
                await collect_position_metrics(client)
            except Exception as exc:
                print(f"Failed to collect metrics: {exc}")
        usage = await client.usage()
        print(f"API使用額度: {usage.bytes/1048576:.2f}/ {usage.limit_bytes/1048576:.2f} MB, 已使用{usage.bytes/usage.limit_bytes*100:.2f}%")


async def start_background_tasks(app: web.Application):
    app["exporter_task"] = asyncio.create_task(update_metrics(app))

async def cleanup_background_tasks(app: web.Application):
    app["exporter_task"].cancel()
    await app["exporter_task"]

app.on_startup.append(start_background_tasks)
app.on_cleanup.append(cleanup_background_tasks)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
