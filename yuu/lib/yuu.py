# pip install fluxer.py[voice]

from fluxer import Client, Intents
from time import sleep
from json import loads
from zoneinfo import ZoneInfo
from datetime import datetime
import socket
import asyncio


class MyClient(Client):
    """
    fluxer.py の `Client` を継承した Bot 本体。

    ## 属性

    | 名前 | 型 | 説明 |
    | --- | --- | --- |
    | `config` | `dict` | `configFile` から読み込んだ設定 |
    | `weekdayName` | `tuple[str, ...]` | 曜日名（日本語） |
    | `TOKEN` | `str` | `TOKENFILE` から読み込んだトークン |
    """

    def __init__(self, TOKENFILE: str = "fluxer.token", configFile: str = "config.json", autorun: bool = True) -> None:
        """
        Bot を初期化する。

        ## 引数

        | 名前 | 型 | デフォルト | 説明 |
        | --- | --- | --- | --- |
        | `TOKENFILE` | `str` | `"fluxer.token"` | トークンが書かれたファイルのパス |
        | `configFile` | `str` | `"config.json"` | 設定ファイルのパス |
        | `autorun` | `bool` | `True` | `True` の場合コンストラクタ内で即座に `run()` する |
        """
        intents = Intents.all()  # MESSAGE_CONTENT を含め全て許可
        super().__init__(intents=intents)

        # fluxer.py の Client は on_message / on_ready を自動では拾わないため、
        # メソッドとして明示的にイベント登録する
        self.event(self.on_ready)
        self.event(self.on_message)

        with open(configFile, "r", encoding="UTF-8") as f:
            self.config = loads(f.read())

        self.weekdayName = ("月", "火", "水", "木", "金", "土", "日")

        self._schedule_task: asyncio.Task | None = None

        while not self.check_network():
            sleep(5)

        with open(TOKENFILE, "r", encoding="UTF-8") as f:
            self.TOKEN = f.read().split("\n")[0]

        if autorun:
            self.run(self.TOKEN)

    def check_network(self, host: str = "8.8.8.8", port: int = 53, timeout: float = 1) -> bool:
        """
        外部ホストへの疎通確認を行う。

        ## 引数

        | 名前 | 型 | デフォルト | 説明 |
        | --- | --- | --- | --- |
        | `host` | `str` | `"8.8.8.8"` | 疎通確認先のホスト |
        | `port` | `int` | `53` | 疎通確認先のポート |
        | `timeout` | `float` | `1` | タイムアウト秒数 |

        ## 戻り値

        | 型 | 説明 |
        | --- | --- |
        | `bool` | 接続できれば `True`、失敗すれば `False` |
        """
        try:
            with socket.socket() as sock:
                sock.settimeout(timeout)
                sock.connect((host, port))
            return True
        except OSError:
            return False

    async def send_message(self, text: str, channelID: int) -> None:
        """
        チャンネルまたはDM宛にメッセージを送信する。

        ## 引数

        | 名前 | 型 | 説明 |
        | --- | --- | --- |
        | `text` | `str` | 送信するテキスト |
        | `channelID` | `int` | 送信先のチャンネルID、またはユーザーID(DM用) |
        """
        channel = None
        try:
            channel = await self.fetch_channel(str(channelID))  # サーバチャンネル用
        except Exception:
            pass

        if channel is None:
            try:
                channel = await self.fetch_user(str(channelID))  # DM用
            except Exception:
                pass

        if channel is not None:
            await channel.send(text)

    def send_discord(self, sendMessage: str, channelID: int) -> None:
        """
        別スレッドから同期的にメッセージ送信を行うためのラッパー。

        ## 引数

        | 名前 | 型 | 説明 |
        | --- | --- | --- |
        | `sendMessage` | `str` | 送信するテキスト |
        | `channelID` | `int` | 送信先のチャンネルID |
        """
        asyncio.run(self.send_message(sendMessage, channelID))

    def __str__(self) -> str:
        return f"{self.user.username} : {self.user.id}"

    async def on_ready(self) -> None:
        """
        起動時（READYイベント受信時）に動作する処理。
        """
        if "adminID" in self.config:
            await self.send_message("ログインしました", self.config["adminID"])
            print(str(self))

        if "autoAllowChannel" in self.config and self._schedule_task is None:
            self._schedule_task = asyncio.create_task(
                self._loop(self.config["autoAllowChannel"])
            )

    async def _loop(self, channelList: list = None, tz: str = "Asia/Tokyo") -> None:
        """
        定時処理。`on_ready` からバックグラウンドタスクとして起動される。

        `fluxer.py` には `discord.ext.tasks` 相当の機能が現状無いため、
        `asyncio` の無限ループで 60 秒間隔の処理を実装している。

        ## 引数

        | 名前 | 型 | デフォルト | 説明 |
        | --- | --- | --- | --- |
        | `channelList` | `list` | `None` | 通知対象のチャンネル情報リスト |
        | `tz` | `str` | `"Asia/Tokyo"` | 日時計算に使うタイムゾーン |
        """
        channelList = channelList or []

        while True:
            try:
                nowTZTime = datetime.now(ZoneInfo(tz))
                nowTZdate = f"{nowTZTime.month}/{nowTZTime.day}"
                nowTZWeekday = self.weekdayName[nowTZTime.weekday()]
                nowTZHour = nowTZTime.hour
                nowTZMinute = nowTZTime.minute
                nowTZSecond = nowTZTime.second

                sendText = ""

                if sendText != "":
                    for channel in channelList:
                        await self.send_message(sendText, channel["id"])
            except Exception:
                # 定時処理内の例外でループ全体が止まらないようにする
                import logging
                logging.exception("定時処理中にエラーが発生しました")

            await asyncio.sleep(60)  # 60秒に一回ループ

    async def on_message(self, message) -> None:
        """
        メッセージ受信時に呼ばれるイベント。

        ## 引数

        | 名前 | 型 | 説明 |
        | --- | --- | --- |
        | `message` | `fluxer.Message` | 受信したメッセージオブジェクト |
        """
        self.message = {}
        self.message["userName"] = str(message.author)
        self.message["channelID"] = message.channel_id

        if (
            message.author.bot or               # メッセージ送信者がBotだった場合は無視する
            not message.content.startswith("$")  # 呼び出しコマンドではない場合は無視する
        ):
            return

        await message.add_reaction("❤️")
        self.message["message"] = str(message.content).lstrip().replace("$", "", 1).replace("\n", "")
        await self.send_message(self.message["message"], self.message["channelID"])
