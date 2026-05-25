import asyncio
import os
from dotenv import load_dotenv
from aiohttp import web
from prometheus_client import Gauge
from prometheus_client.aiohttp import make_aiohttp_handler
from shioaji import FuturePosition, StockPosition

from list_holdings import HoldingsClient

load_dotenv()

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

app = web.Application()
app.router.add_get("/metrics", make_aiohttp_handler())

LAST_POSITION_LABELS: set[str] = set()
EXPORT_INTERVAL_SECONDS = 300

def set_position_metrics(position: StockPosition | FuturePosition) -> None:
    code = position.code
    POSITION_PRICE.labels(code).set(position.price)
    POSITION_PNL.labels(code).set(position.pnl)


def remove_position_metrics(code: str) -> None:
    POSITION_PRICE.remove(code)
    POSITION_PNL.remove(code)


async def collect_position_metrics(client: HoldingsClient) -> None:
    await client.ensure_logged_in()
    positions = await client.list_positions()
    current_labels: set[str] = set()

    for position in positions.values():
        code = str(getattr(position, "code", ""))
        if not code:
            continue
        current_labels.add(code)
        set_position_metrics(position)

    stale_labels = LAST_POSITION_LABELS - current_labels
    for code in stale_labels:
        remove_position_metrics(code)

    LAST_POSITION_LABELS.clear()
    LAST_POSITION_LABELS.update(current_labels)


async def update_metrics(app):
    client = HoldingsClient()
    while True:
        try:
            await collect_position_metrics(client)
        except Exception as exc:
            print(f"Failed to collect metrics: {exc}")
        await asyncio.sleep(EXPORT_INTERVAL_SECONDS)

async def start_background_tasks(app: web.Application):
    app["exporter_task"] = asyncio.create_task(update_metrics(app))

app.on_startup.append(start_background_tasks)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))