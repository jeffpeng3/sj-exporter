import asyncio
from os import getenv
from dotenv import load_dotenv
import shioaji as sj

load_dotenv()


class HoldingsClient:
    def __init__(self):
        self.api_key: str = getenv("SJ_API_KEY")  # type: ignore
        if not isinstance(self.api_key, str) or not self.api_key:
            raise EnvironmentError("SJ_API_KEY must be set in environment variables")
        self.secret_key: str = getenv("SJ_SEC_KEY")  # type: ignore
        if not isinstance(self.secret_key, str) or not self.secret_key:
            raise EnvironmentError(
                "SJ_API_KEY and SJ_SEC_KEY must be set in environment variables"
            )
        self.api = sj.ShioajiAsync()
        self.account: sj.Account | None = None
        asyncio.create_task(self.login())

    async def ensure_logged_in(self):
        while not self.account:
            print("尚未登入，正在等待...")
            await asyncio.sleep(0.1)

    @staticmethod
    def format_position(position: sj.StockPosition) -> str:

        fields = [
            f"code={position.code}",
            f"quantity={position.quantity}",
            f"price={position.price}",
            f"last_price={position.last_price}",
            f"pnl={position.pnl}",
        ]
        return ", ".join(fields)

    @staticmethod
    def positions_by_code(
        positions: list[sj.StockPosition | sj.FuturePosition],
    ) -> dict[str, sj.StockPosition]:
        positions_dict: dict[str, sj.StockPosition] = {}
        for position in positions:
            code = position.code
            if code:
                positions_dict[code] = position # type: ignore
        return positions_dict

    @staticmethod
    def position_roi(position: sj.StockPosition) -> float:
        cost = position.price * position.quantity
        if not cost:
            return 0.0
        return position.pnl / cost * 100

    @staticmethod
    def print_positions(
        positions_dict: dict[str, sj.StockPosition],
    ) -> None:
        if not positions_dict:
            print("目前沒有任何持倉")
            return

        total_cost = 0.0
        total_pnl = 0.0

        print("持倉列表")
        print("-" * 100)
        print(
            "code\tquantity\tprice\tlast_price\tpnl\troi(%)"
        )

        for code, position in sorted(positions_dict.items()):
            roi = HoldingsClient.position_roi(position)
            cost = position.price * position.quantity
            total_cost += cost
            total_pnl += position.pnl
            print(
                "\t".join(
                    str(x)
                    for x in [
                        code,
                        position.quantity,
                        position.price,
                        position.last_price,
                        position.pnl,
                        f"{roi:.2f}",
                    ]
                )
            )

        overall_roi = (total_pnl / total_cost * 100) if total_cost else 0.0
        print("-" * 100)
        print(
            f"總成本: {total_cost:.2f}\t總損益: {total_pnl:.2f}\tROI: {overall_roi:.2f}%"
        )

    async def login(self):
        await self.api.login(
            api_key=self.api_key,
            secret_key=self.secret_key,
            fetch_contract=False,
        )
        self.account = self.api.stock_account

    async def refresh_token(self):
        print("正在刷新Token...")
        try:
            await self.api.logout()
        except Exception as e:
            print(f"登出失敗: {e}")
        self.account = None
        await self.login()

    async def usage(self) -> sj.UsageOut:
        usage = await self.api.usage()
        return usage

    async def list_positions(self) -> dict[str, sj.StockPosition]:
        positions = await self.api.list_positions(self.account, unit="Share")
        positions_dict = self.positions_by_code(positions)
        return positions_dict


async def main():
    client = HoldingsClient()
    await client.ensure_logged_in()
    while True:
        try:
            positions = await client.list_positions()
            client.print_positions(positions)
            await asyncio.sleep(10)
        except KeyboardInterrupt:
            break
        except asyncio.CancelledError:
            break
    usage = await client.usage()
    print(f"API使用額度: {usage.bytes/1048576:.2f}/ {usage.limit_bytes/1048576:.2f} MB, 已使用{usage.bytes/usage.limit_bytes*100:.2f}%")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
