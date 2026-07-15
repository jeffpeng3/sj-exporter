import aiohttp
import asyncio
import xml.etree.ElementTree as ET
import exchange_calendars as xcals
from datetime import date, datetime
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

        if "限制存取間隔時間" in text:
            await asyncio.sleep(3.5)
            async with session.get(url) as response2:
                text = await response2.text()

        root = ET.fromstring(text)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "cap": "urn:oasis:names:tc:emergency:cap:1.1",
        }
        today = datetime.now(tz=tz).date()

        for entry in root.findall("atom:entry", ns):
            summary = entry.findtext("atom:summary", "", ns)
            if "臺北市" not in summary or "停止上班" not in summary:
                continue

            effective = entry.find("cap:effective", ns)
            expires = entry.find("cap:expires", ns)
            if effective is None or expires is None:
                continue

            eff_date = _parse_cap_date(effective.text)
            exp_date = _parse_cap_date(expires.text)
            if eff_date and exp_date and eff_date <= today <= exp_date:
                return True

        return False
    except Exception as e:
        print(f"NCDR API 檢查失敗: {e}")
        return False


def _parse_cap_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    date_part = date_str.split()[0]
    try:
        parts = date_part.split("/")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return None

async def main():
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        scheduled_trading_day = is_scheduled_trading_day()
        print(f"Is today a scheduled trading day? {scheduled_trading_day}")
        typhoon_closed = await is_typhoon_closed_today(session)
        print(f"Is today a typhoon closure day? {typhoon_closed}")


if __name__ == "__main__":
    asyncio.run(main())