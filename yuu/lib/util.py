import os, subprocess, json, sqlite3, re, jaconv, random, requests
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
import psutil
from datetime import timedelta, datetime

def cmd(command):
    try:
        r = subprocess.check_output(command, shell=True)
        return r.decode("shift-jis").strip()
    except:
        return 1


def web_scraping(url, tag = "html", num = -1, attribute = "text"):
    response = requests.get(url)
    response.encoding = response.apparent_encoding
    contents = BeautifulSoup(response.text, 'html.parser')
    
    tagList = contents.select(tag)
    if num < 0:
        return tagList
    if attribute == "text":
        value = tagList[num].getText()
    else:
        value = tagList[num].get(attribute)
    
    return value

def get_pc_status():
    mem = psutil.virtual_memory() # メモリ使用率
    cpu = psutil.cpu_percent(interval=1) # CPU使用率
    return [cpu, mem.percent]

class MySQLite():
    def __init__(self, db = f"{os.path.dirname(os.path.abspath(__file__))}/sqlite3.db"):
        # データベースとの接続
        self.databaseHost = sqlite3.connect(database = db)
    
    def __enter__(self):
        # カーソルを作る
        self.database = self.databaseHost.cursor()
        return self
    
    def send_sql(self, sql): # SQL文送信
        self.database.execute(sql)
        self.db_commit()
        return self.database.fetchall() # タプル形式で全て取得
    
    def db_commit(self):
        self.databaseHost.commit()

    def __exit__(self, *args):
        self.db_commit()
        self.database.close()
        self.databaseHost.close()

class CreateMessage(MySQLite):
    def __init__(
        self, 
        admin, 
        db = f"{os.path.dirname(os.path.abspath(__file__))}/sqlite3.db", 
        eventFilePath = f"{os.path.dirname(os.path.abspath(__file__))}/event.json",
        readme = f"{os.path.dirname(os.path.abspath(__file__))}/README.md"
    ):
        self.nowTime            = datetime.now(ZoneInfo("Asia/Tokyo"))
        self.weekdayName        = ("月","火","水","木","金","土","日")
        super().__init__(db)
        self.admin              = admin
        self.hiragana           = re.compile(r'[\u3041-\u3096]') #ひらがなの登録
        self.katakana           = re.compile(r'[\u30A0-\u30FA]') #カタカナの登録
        self.eventFilePath      = eventFilePath
        self.readmePath         = readme

    def classify_message(self, message, mode:int):
        self.message            = message
        if self.message == "":
            self.categoryData = "callYuu"
            return
        try:
            self.categoryData   = self.send_sql(f"""
                SELECT category FROM emotion 
                    WHERE "{self.message}" LIKE "%" || data || "%"
                    AND page = {mode}
                    ORDER BY id ASC
            """)[0][0]
        except:
            self.categoryData   = "NotFound"
    
    def get_message(self):
        if self.categoryData.count("date")>0:
            return  f"{self.nowTime.year}年 {self.nowTime.month}月 {self.nowTime.day}日 {self.weekdayName[self.nowTime.weekday()]}曜日だよ"
        elif self.categoryData.count("time")>0:
            return f"{self.nowTime.hour}:{self.nowTime.minute}だよ"
        elif self.categoryData.count("weather")>0:
            url = self.get_weather_url()
            weatherData     = requests.get(url)
            weatherJSONData = json.loads(weatherData.text)
            if self.message.count("明日") > 0:
                dateNumber = 1
            elif self.message.count("明後日") > 0:
                dateNumber = 2
            else:
                dateNumber = 0
            weatherDate = weatherJSONData["forecasts"][dateNumber]["date"]
            weartherTitle = weatherJSONData["title"]
            if dateNumber == 2:
                weather = weatherJSONData["forecasts"][dateNumber]["telop"]
            else:
                weather = weatherJSONData["forecasts"][dateNumber]["detail"]["weather"]
            tempMin = weatherJSONData["forecasts"][dateNumber]["temperature"]["min"]["celsius"]
            tempMax = weatherJSONData["forecasts"][dateNumber]["temperature"]["max"]["celsius"]
            telop = weatherJSONData["description"]["text"].replace("　","")
            chanceOfRain0_6 = weatherJSONData["forecasts"][dateNumber]["chanceOfRain"]["T00_06"]
            chanceOfRain6_12 = weatherJSONData["forecasts"][dateNumber]["chanceOfRain"]["T06_12"]
            chanceOfRain12_18 = weatherJSONData["forecasts"][dateNumber]["chanceOfRain"]["T12_18"]
            chanceOfRain18_24 = weatherJSONData["forecasts"][dateNumber]["chanceOfRain"]["T18_24"]
            chanceOfRain = f"""
0時～6時 : {chanceOfRain0_6}
6時～12時 : {chanceOfRain6_12}
12時～18時 : {chanceOfRain12_18}
18時～24時 : {chanceOfRain18_24}
            """
            svgWeatherURL = weatherJSONData["forecasts"][dateNumber]["image"]["url"]
            return f"""{str(weatherDate)}の{weartherTitle}は{weather}"""
        
        elif self.categoryData.count("morse")>0:
            return f"""
```
{
    self.exchange(
        morsestr = self.message.split("モールス信号:")[1]
    )
}
```
            """
        
        elif self.categoryData.count("jamcode")>0:
            return self.morse_decode(
                morseCode = self.message.split("日文モールス復号:")[1],
                lang = "ja"
            )
        elif self.categoryData.count("eumcode")>0:
            return self.morse_decode(
                morseCode = self.message.split("欧文モールス復号:")[1],
                lang = "eu"
            )
        
        elif self.categoryData.count("prof") > 0:
            with open(f"{self.readmePath}", "r", encoding="UTF-8") as readme:
                return f"""\
{readme.read()}

> 何かあれば管理者<@{self.admin}>まで
"""
            
        elif self.categoryData.count("reminder") > 0:
            arrangedMessage = self.message.split("リマインダ:")[1]
            time = 0
            timerFlag = 1
            if arrangedMessage.count("時間") > 0:
                hourMessage = re.findall(r"\d+",arrangedMessage.split("時間")[0])[-1]
            elif arrangedMessage.count("時") > 0:
                hourMessage = re.findall(r"\d+",arrangedMessage.split("時")[0])[-1]
                timerFlag = 0
            else:
                hourMessage = 0
            if arrangedMessage.count("分") > 0:
                minuteMessage = re.findall(r"\d+",arrangedMessage.split("分")[0])[-1]
            else:
                minuteMessage = 0
            if arrangedMessage.count("秒") > 0:
                secondMessage = re.findall(r"\d+",arrangedMessage.split("秒")[0])[-1]
            else:
                secondMessage = 0
            if timerFlag == 1:
                self.reminderTime = float(hourMessage) * 3600 + float(minuteMessage) * 60 + float(secondMessage)
                
            else:
                nowTime = self.nowTime
                reminderTime = datetime(year=self.nowTime.year, month=self.nowTime.month, day=self.nowTime.day, hour=int(hourMessage), minute = int(minuteMessage), second = int(secondMessage))
                if nowTime > reminderTime: 
                    # timedelta 使う
                    self.reminderTime = datetime(
                        year=self.nowTime.year, 
                        month=self.nowTime.month, 
                        day=int(self.nowTime.day), 
                        hour=int(hourMessage), 
                        minute = int(minuteMessage), 
                        second = int(secondMessage)
                    ) + timedelta(days = 1)
                timeDelta = reminderTime - nowTime
                self.reminderTime = timeDelta.total_seconds()
            return self.categoryData
            
        elif self.categoryData.count("calc")>0:
            if self.message.count("計算:") > 0:
                calc = self.message.split("計算:")[1]
            else:
                calc = self.message.split("calc")[1]
            
            try:
                regEx = r"\d+|\+|\-|\*|\/|\%|\(|\)|\."
                calc = re.findall(regEx, calc)
                calc = "".join(calc)
                return eval(calc)
            except:
                return self.categoryData
            
        elif (
            self.categoryData.count("stop")     > 0 or
            self.categoryData.count("events")   > 0 or
            self.categoryData.count("weather")  > 0 or
            self.categoryData.count("search")   > 0 or
            self.categoryData.count("whoami")   > 0 or
            self.categoryData.count("server")   > 0 or
            self.categoryData.count("usecmd")   > 0 or
            self.categoryData.count("lock")     > 0 or
            self.categoryData.count("help")     > 0 or
            self.categoryData.count("chgun")    > 0 or
            self.categoryData.count("fav")      > 0 or
            self.categoryData.count("del")      > 0 or
            self.categoryData.count("music")    > 0
        ):
            return self.categoryData
        
        elif self.categoryData.count("health")>0:
            cpu, mem = get_pc_status()
            if float(mem) > 60:
                return "ペンちゃんがこき使ってくる...\n頭パンクしそうだよ..."
            elif float(cpu) > 60:
                return "證鷹℃縺弱□繧医≦...蜉ｩ縺代※..."
            elif float(mem) > 30:
                return "ペンちゃんがなんか重いアプリ開いてるから、処理を頑張っているのだ...！\n偉いでしょ(*´ω｀*)〜♪"
            else:
                return "元気だよ！ありがと(*´ω｀*)〜♪"
        
        elif self.categoryData.count("callYuu") > 0:
            return "何？"

        else:
            replyData = self.send_sql(f"""
                SELECT value FROM keywordlist
                WHERE key = "nevertheless"
            """)
            for n in replyData:
                if int(self.message.count(n[0])) > 0:
                    self.message = self.message.split(n[0])[-1]

            self.classify_message(self.message, 1)
            try:
                rep = self.send_sql(f"""
                    SELECT value FROM keywordlist
                        WHERE "{self.categoryData}" LIKE "%" || key || "%"
                """)
                ansIndex = random.randint(0, len(rep)-1) # 最小値以上最大値以下の整数
                return rep[ansIndex][0]
            except:
                if self.categoryData == "NotFound":
                    self.classify_message(self.message, 2)
                    replyData = self.send_sql(f"""
                        SELECT value FROM keywordlist
                        WHERE key = "firstPerson"
                    """)
                    if self.categoryData.count("askName") >0:
                        for n in replyData:
                            if int(self.message.count(n[0])) > 0:
                                return "callyou"
                        return "私は、ユウって名前だよ！\nよろしくね！！"

                    elif self.categoryData.count("callYuu") > 0:
                        return "何？"

                    elif self.categoryData == "question":
                        return f"私、Botだからよくわかんないや\n<@{self.admin}>に聞いて"
                    
                return self.categoryData
            
            
        
    def ev(self, day):# 特別な日付の時の処理 db化したい
        with open(self.eventFilePath,'r',encoding="UTF-8") as eventFile:
            eventData = json.loads(eventFile.read())

        value = [day, "True"]

        for e in eventData:
            eventDay = e["date"]
            event = e["value"]
            if str(day) == str(eventDay):
                value = [day.replace(eventDay, event), e["adminOnly"]]
                break
        return value
    
    def get_event(self, messageChannelID):
        # 今日のイベント取得
        nowJPNdate          = f"{self.nowTime.month}/{self.nowTime.day}"
        eventSearchValue    = self.ev(nowJPNdate)
        todayEvent          = eventSearchValue[0]
        adminOnly           = eventSearchValue[1]
        self.event          = f"{nowJPNdate}:特に何もないよ"
        if todayEvent != nowJPNdate:
            if adminOnly == "False":
                self.event = f"{nowJPNdate}:{todayEvent}"
            else:
                if str(messageChannelID) == str(self.admin):
                    self.event = f"{nowJPNdate}:{todayEvent}"
        
        return self.event
    
    def get_reminder(self):
        return self.reminderTime

    def get_weather_url(self):
        jsonURL = "https://weather.tsukumijima.net/api/forecast/city/"
        try:
            cityID = self.send_sql(f"""
                SELECT id FROM weather 
                    WHERE "{self.message}" LIKE "%" || prefecture || "%"
                    ORDER BY id ASC
            """)[0][0]
            
        except:
            cityID              = "130010"
        return f"{jsonURL}{cityID}"
        
    def exchange(self, morsestr):
        val = []
        for code in morsestr:
            if code == "　":
                code = "space"
            elif code == " ":
                code = "space"
            elif code == "゛":
                code = "濁点"
            elif code == "゜":
                code = "半濁点"
                
            elif (self.hiragana.search(code) is not None):
                hkataka = jaconv.hira2hkata(code)
                hkm = jaconv.h2z(hkataka[0])
                try:
                    hka = jaconv.h2z(hkataka[1])
                    val.append(
                        self.send_sql(f"""
                            SELECT value FROM morse
                            WHERE data = "{jaconv.kata2hira(hkm)}"
                        """)[0][0]
                    )
                    if hka == '\uFF9E':
                        code = "濁点"
                    elif hka == '\uFF9F':
                        code = "半濁点"
                
                except IndexError:
                    hka = ""

            elif (self.katakana.search(code) is not None):
                hkataka = jaconv.z2h(code)
                hkm = jaconv.h2z(hkataka[0])
                try:
                    hka = jaconv.h2z(hkataka[1])
                    val.append(
                        self.send_sql(f"""
                            SELECT value FROM morse
                            WHERE data = "{jaconv.kata2hira(hkm)}"
                        """)[0][0]
                    )
                    if hka == '\uFF9E':
                        code = "濁点"
                    elif hka == '\uFF9F':
                        code = "半濁点"
                
                except IndexError:
                    hka = ""
                    code = jaconv.kata2hira(hkm)
            else:
                code = code.lower()

            if code == "space":
                val.append(" ")
            else:
                try:
                    val.append(
                        self.send_sql(f"""
                            SELECT value FROM morse
                            WHERE data = "{code}"
                        """)[0][0]
                    )
                except:
                    val.append("")

        return " ".join(val)
    
    def morse_decode(self, morseCode:str, lang = "ja"):
        morseCodeData = morseCode.split(" ")
        ans = ""
        language = lang
        if language != "ja":
            language = "en"
        for mcode in morseCodeData:
            try:
                if mcode == "":
                    ans += " "
                    
                else:
                    code = self.send_sql(f"""
                        SELECT data FROM morse
                        WHERE value = "{mcode}"
                        AND (
                            lang = "{language}" OR
                            lang = "base"
                        )

                    """)[0][0]
                    if code == "濁点":
                        ans += "゛"
                    elif code == "半濁点":
                        ans += "゜"
                    else:
                        ans += code
            except:
                ans += " "
        return ans