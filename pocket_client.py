"""
Market data feed adapter.

Two backends:
  - SimulatedFeed:     random-walk price generator, no credentials needed.
                        Use this to test the bot's formatting/scheduling
                        before wiring up a live feed.
  - PocketOptionFeed:  thin adapter around your existing Pocket Option
                        connection. If you already have the WebSocket /
                        SafePocketClient code from MONEYBOT AI, plug its
                        candle-fetch call into `_fetch_closes` below -
                        the rest of this bot only needs a list of recent
                        closing prices per pair, so it doesn't care how
                        you get them.
"""
import random
import time
from abc import ABC, abstractmethod
from typing import List


class BaseFeed(ABC):
    @abstractmethod
    async def get_recent_closes(self, pair: str, timeframe_seconds: int, count: int) -> List[float]:
        ...


class SimulatedFeed(BaseFeed):
    """Deterministic-ish random walk per pair, seeded by pair name so runs are repeatable."""

    def __init__(self):
        self._state = {}

    def _seed(self, pair: str) -> float:
        if pair not in self._state:
            base = 1.0 + (abs(hash(pair)) % 1000) / 1000
            self._state[pair] = base
        return self._state[pair]

    async def get_recent_closes(self, pair: str, timeframe_seconds: int, count: int) -> List[float]:
        price = self._seed(pair)
        closes = []
        rnd = random.Random(pair + str(int(time.time() // timeframe_seconds)))
        for _ in range(count):
            price += rnd.uniform(-0.0006, 0.0006)
            closes.append(round(price, 5))
        self._state[pair] = price
        return closes


class PocketOptionFeed(BaseFeed):
    """
    Wraps a real Pocket Option connection.

    Fill in `_fetch_closes` to call whatever client you're already using
    (e.g. your SafePocketClient wrapper). This class deliberately only
    reads market data - it never places trades, since signals here are
    for manual execution.
    """

    def __init__(self, ssid: str, demo: bool = True):
        self.ssid = ssid
        self.demo = demo
        self._client = None  # lazily connected

    async def _connect(self):
        if self._client is not None:
            return
        # TODO: plug in your existing Pocket Option client here, e.g.:
        #
        #   from pocket_option_api import PocketOptionAPI
        #   self._client = PocketOptionAPI(ssid=self.ssid, demo=self.demo)
        #   await self._client.connect()
        #
        raise NotImplementedError(
            "Wire up your Pocket Option client in PocketOptionFeed._connect(). "
            "Until then, use SimulatedFeed to test the rest of the bot."
        )

    async def get_recent_closes(self, pair: str, timeframe_seconds: int, count: int) -> List[float]:
        await self._connect()
        # TODO: replace with your client's real candle-fetch call, e.g.:
        #
        #   candles = await self._client.get_candles(pair, timeframe_seconds, count)
        #   return [c["close"] for c in candles]
        #
        raise NotImplementedError("Wire up candle fetching in PocketOptionFeed.get_recent_closes().")
