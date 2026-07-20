# pip install fluxer.py[voice]

from fluxer import Client, Intents
from time import sleep
from json import loads
from zoneinfo import ZoneInfo
from datetime import datetime
import socket
import asyncio

from .util import CreateMessage


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

    def __init__(self, BASEDIR, TOKENFILE: str = "fluxer.token", configFile: str = "config.json", autorun: bool = True) -> None:
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

        self.BASEDIR = BASEDIR

        with open(f"{self.BASEDIR}/{configFile}", "r", encoding="UTF-8") as f:
            self.config = loads(f.read())

        self.weekdayName = ("月", "火", "水", "木", "金", "土", "日")

        self._schedule_task: asyncio.Task | None = None

        while not self.check_network():
            sleep(5)

        with open(f"{self.BASEDIR}/{TOKENFILE}", "r", encoding="UTF-8") as f:
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

    def send(self, sendMessage: str, channelID: int) -> None:
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
                with CreateMessage(
                    admin           = f"""{self.config["adminID"]}""", 
                    db              = f"""{self.BASEDIR}/{self.config["emotionFile"]}""", 
                    eventFilePath   = f"""{self.BASEDIR}/{self.config["eventFilePath"]}""",
                    readme          = f"""{self.BASEDIR}/{self.config["README"]}"""
                ) as msg:
                    eventSearchValue = msg.ev(nowTZdate)
                todayEvent = eventSearchValue[0]
                adminOnly = eventSearchValue[1]

                eventFlag = 0
        
                if nowTZHour == 0 and nowTZMinute == 0:
                    sendText = f"日付が変わりました。\n今日は{nowTZdate}です。"
                    if todayEvent != nowTZdate:
                        eventFlag = 1
    
                elif nowTZHour == 6 and nowTZMinute == 0:
                    if todayEvent != nowTZdate:
                        eventFlag = 1
                    if nowTZWeekday == self.weekdayName[0]:
                        sendText = f"おはようございます！\n今日は{nowTZdate}月曜日！\n一週間の始まり...\n体調に気を付けて今週も頑張りましょう！！"
                    elif nowTZWeekday == self.weekdayName[2]:
                        sendText = "おはようございます！\n今日は一週間の折り返し地点の水曜日です！！\nあと半分で休日ですよ(:3_ヽ)_"
                    elif nowTZWeekday == self.weekdayName[4]:
                        sendText = f"おはようございます！\n今日は{nowTZdate}金曜日！！\n今日が終われば休みが待ってます！！\n頑張りましょ(:3_ヽ)_"
                    else:
                        sendText = f"おはようございます！\n今日は{nowTZdate}\n今日も一日体調に気を付けて過ごしましょ！"

                elif nowTZHour == 12 and nowTZMinute == 0:
                    sendText = "お昼です。\n皆さん休みましょう！！"

                elif nowTZHour == 0 and nowTZMinute == 15:
                    sendText = "おやすみzzz..."
                    with open(f"""{self.BASEDIR}/{self.config["tempFile"]}""","w",encoding="UTF-8") as tempFile:
                        tempFile.write("U,WORD")

                if sendText != "":
                    for channelID in channelList:
                        await self.send_message(sendText, channelID)

                if eventFlag == 1:
                    if adminOnly == "False":
                        for channelID in channelList:
                            await self.send_message(f"今日は{todayEvent}", channelID)
                    else:
                        await self.send_message(f"""今日は{todayEvent}""", self.config["adminID"])

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

        arrangedMessage = str(message.content).lstrip().replace("$", "", 1).replace("\n", "")

        with CreateMessage(
            admin           = f"""{self.config["adminID"]}""", 
            db              = f"""{self.BASEDIR}/{self.config["emotionFile"]}""", 
            eventFilePath   = f"""{self.BASEDIR}/{self.config["eventFilePath"]}""",
            readme          = f"""{self.BASEDIR}/{self.config["README"]}"""
        ) as msg:
            msg.classify_message(arrangedMessage, 1)
            sendTimeLineMessage = msg.get_message()

        self.message["message"] = str(sendTimeLineMessage)
        await self.send_message(self.message["message"], self.message["channelID"])
