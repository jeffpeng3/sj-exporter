import aiohttp
import asyncio
import exchange_calendars as xcals
from datetime import datetime
from zoneinfo import ZoneInfo
tz = ZoneInfo("Asia/Taipei")

def is_scheduled_trading_day():
    twse = xcals.get_calendar("XTAI")
    return twse.is_session(datetime.now(tz=tz).date())

async def is_typhoon_closed_today(session: aiohttp.ClientSession):
    url = "https://alerts.ncdr.nat.gov.tw/RssAtomFeed.ashx?AlertType=33"
    try:
        async with session.get(url) as response:
            text = await response.text()
            if "臺北市" in text and "停止上班" in text:
                return True
        return False
    except Exception as e:
        print(f"NCDR API 檢查失敗: {e}")
        return False

async def main():
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        scheduled_trading_day = is_scheduled_trading_day()
        print(f"Is today a scheduled trading day? {scheduled_trading_day}")
        typhoon_closed = await is_typhoon_closed_today(session)
        print(f"Is today a typhoon closure day? {typhoon_closed}")


if __name__ == "__main__":
    asyncio.run(main())