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
    def format_position(position) -> str:
        fields = [
            f"code={getattr(position, 'code', '')}",
            f"direction={getattr(position, 'direction', '')}",
            f"quantity={getattr(position, 'quantity', '')}",
            f"price={getattr(position, 'price', '')}",
            f"last_price={getattr(position, 'last_price', '')}",
            f"pnl={getattr(position, 'pnl', '')}",
            f"cond={getattr(position, 'cond', '')}",
        ]
        return ", ".join(fields)

    @staticmethod
    def positions_by_code(
        positions: list[sj.StockPosition | sj.FuturePosition],
    ) -> dict[str, sj.StockPosition | sj.FuturePosition]:
        return {
            position.code: position
            for position in positions
            if getattr(position, "code", "")
        }

    @staticmethod
    def print_positions(
        positions_dict: dict[str, sj.StockPosition | sj.FuturePosition],
    ) -> None:
        if not positions_dict:
            print("目前沒有任何持倉")
            return

        print("持倉列表")
        print("-" * 80)
        print(
            "code\tquantity\tprice\tlast_price\tpnl"
        )

        for code, position in sorted(positions_dict.items()):
            print(
                "\t".join(
                    str(x)
                    for x in [
                        code,
                        position.quantity,
                        position.price,
                        position.last_price,
                        position.pnl,
                    ]
                )
            )
        print("-" * 80)

    async def login(self):
        await self.api.login(
            api_key=self.api_key,
            secret_key=self.secret_key,
            fetch_contract=False,
        )
        self.account = self.api.stock_account

    async def list_positions(self) -> dict[str, sj.StockPosition | sj.FuturePosition]:
        positions = await self.api.list_positions(self.account, unit="Share")
        positions_dict = self.positions_by_code(positions)
        return positions_dict


async def main():
    client = HoldingsClient()
    await client.ensure_logged_in()
    positions = await client.list_positions()
    client.print_positions(positions)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
