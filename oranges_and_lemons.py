from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QVBoxLayout, QPushButton, QDialog, QTableWidgetItem,
    QLabel, QWidget, QGridLayout, QFrame, QScrollArea, QTableWidget, QSizePolicy
)
from PySide6.QtCore import (
    Signal, QTimer, QObject, Qt
)
from PySide6.QtGui import QIcon
from enum import IntEnum
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import os, sys, random, math


WIDTH = 1400
HEIGHT = 800
MARGIN = 50
GAMETIME = 900 # 900
O1PROB = 6.0/GAMETIME # 0.000667 for 900
L1PROB = 7.5/GAMETIME # 0.000833 for 900
O2PROB = random.randint(4,8) / GAMETIME
L2PROB = random.uniform(6.5, 14.5 + 1e-9) / GAMETIME
PROB_NOISE_SCALE = 0.0003  # ±0.0001 variation
O1PROB_NOISY = O1PROB + random.uniform(-PROB_NOISE_SCALE, PROB_NOISE_SCALE)
L1PROB_NOISY = L1PROB + random.uniform(-PROB_NOISE_SCALE, PROB_NOISE_SCALE)
O2PROB_NOISY = O2PROB + random.uniform(-PROB_NOISE_SCALE, PROB_NOISE_SCALE)
L2PROB_NOISY = L2PROB + random.uniform(-PROB_NOISE_SCALE, PROB_NOISE_SCALE)

class Side(IntEnum):
    IGNORED = 0
    BUY = 1
    SELL = 2

class Signals(QObject):
    balanceChanged = Signal(float)
    buy = Signal(float)
    sell = Signal(float)
    traded = Signal(object)
    fruitChanges = Signal(int, int, int, int)
    timeChanged = Signal(int) # in seconds
    gameOver = Signal()
    def __init__(self):
        super().__init__()

signals = Signals()

def simulate_final_counts():
    """Run one game and return (o1, l1, o2, l2) at t = GAMETIME."""
    o1 = l1 = o2 = l2 = 0
    p_o1 = O1PROB
    p_l1 = L1PROB
    p_o2 = O2PROB
    p_l2 = L2PROB 

    for _ in range(GAMETIME):
        if random.random() < p_o1: o1 += 1
        if random.random() < p_l1: l1 += 1
        if random.random() < p_o2: o2 += 1
        if random.random() < p_l2: l2 += 1
    return o1, l1, o2, l2



class Panel(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedSize(WIDTH//2 - MARGIN, HEIGHT//2 - MARGIN)
        self.setFrameShape(QFrame.StyledPanel)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

class TradeHistory(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedSize(WIDTH//5, HEIGHT - MARGIN * 1.45)
        self.setFrameShape(QFrame.StyledPanel)

        # Main layout for the panel
        self.layout = QVBoxLayout(self)

        # Scroll area to hold history labels
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.layout.addWidget(self.scroll)

        # Container widget inside scroll area
        self.container = QWidget()
        self.historyLayout = QVBoxLayout(self.container)
        self.historyLayout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.container)

        # Connect signals
        signals.buy.connect(self.captureBuy)
        signals.sell.connect(self.captureSell)
        signals.traded.connect(self.captureTrade)

    def addLabel(self, label: QLabel):
        label.setContentsMargins(0, 0, 0, 8)
        self.historyLayout.insertWidget(0, label)

    def captureBuy(self, price: float):
        label = QLabel(f"total oranges * total lemons\nBuy @ {price:.2f}")
        label.setStyleSheet("color: #80EF80; font-size: 16px;")
        self.addLabel(label)

    def captureSell(self, price: int):
        label = QLabel(f"total oranges * total lemons\nSell @ {price:.2f}")
        label.setStyleSheet("color: #FF6961; font-size: 16px;")
        self.addLabel(label)

    def captureTrade(self, trade):
        desc = getattr(trade, 'text', 'Trade')
        price = getattr(trade, 'value', 0.0)
        action = 'Buy' if trade.side == Side.BUY else 'Sell'
        label = QLabel(f"{desc}\n{action} @ {price}")
        color = '#80EF80' if trade.side == Side.BUY else '#FF6961'
        label.setStyleSheet(f"color: {color}; font-size: 16px;")
        self.addLabel(label)

class TrackerInfo(QFrame):
    def __init__(self):
        super().__init__()

        # underlying value
        self.underlyingValue = 0

        # tracks states internally
        self.o1 = 0
        self.l1 = 0
        self.o2 = 0
        self.l2 = 0
        self.time = 0 # in seconds

        self.setFixedSize(WIDTH//2.5 - MARGIN, HEIGHT//1.5 - MARGIN)
        self.setFrameShape(QFrame.StyledPanel)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.tradeLabel = QLabel("total oranges * total lemons")
        self.tradeLabel.setAlignment(Qt.AlignCenter)
        self.tradeLabel.setStyleSheet("font-size: 24px;")
        self.layout.addWidget(self.tradeLabel)
        
        self.underlyingInfoLabel = QLabel("")
        self.underlyingInfoLabel.setAlignment(Qt.AlignCenter)
        self.underlyingInfoLabel.setStyleSheet("font-size: 32px;")

        plt.style.use("ggplot")
        self.fig, self.ax = plt.subplots(figsize=(4,2))
        self.fig.subplots_adjust(left=0.09, right=0.97, top=0.98, bottom=0.1)
        self.line, = self.ax.plot([], [], lw=2)

        self.ax.grid(False)
        self.ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        self.ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)

        self.ax.margins(x=0.05, y=0.05)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setFixedSize(WIDTH//2.5 - MARGIN, HEIGHT//2.75 + MARGIN)
        self.layout.addWidget(self.canvas)
        self.series_x, self.series_y = [], []


        self.buttonsLayout = QHBoxLayout()
        self.buyButton = QPushButton("Buy", clicked = self.buy)
        self.buyButton.setFixedSize(100, 30)
        self.sellButton = QPushButton("Sell", clicked = self.sell)
        self.sellButton.setFixedSize(100, 30)
        self.buttonsLayout.addWidget(self.buyButton)
        self.buttonsLayout.addWidget(self.sellButton)

        self.layout.addWidget(self.underlyingInfoLabel)
        self.layout.addLayout(self.buttonsLayout)

        signals.fruitChanges.connect(self.getFruitValues)
        signals.timeChanged.connect(self.getTime)

        self.timer = QTimer()
        self.timer.timeout.connect(self.updateUnderlying)
        self.timer.start(1000)

        self.updateUnderlying()
    
    def buy(self):
        signals.buy.emit(float(self.underlyingValue))
    
    def sell(self):
        signals.sell.emit(float(self.underlyingValue))

    def getFruitValues(self, o1, l1, o2, l2):
        self.o1 = o1
        self.l1 = l1
        self.o2 = o2
        self.l2 = l2
    
    def getTime(self, time):
        self.time = time

    def updateUnderlying(self):
        K_REVERT = 0.4                # 0–1  : 0 = pure random walk, 1 = snap to EV
        SIGMA0   = 1.8                 # base volatility
        SIGMA_FLOOR = 1.0
        totalOranges = self.o1 + self.o2
        totalLemons = self.l1 + self.l2
        T = GAMETIME - self.time
        expectedOranges = T * (O1PROB_NOISY + O2PROB_NOISY)
        expectedLemons = T * (L1PROB_NOISY + L2PROB_NOISY)
        ev = totalOranges * totalLemons
        ev += totalOranges * expectedLemons
        ev += totalLemons * expectedOranges
        ev += expectedOranges * expectedLemons
        self.underlyingValue = ev
        self.underlyingInfoLabel.setText(f"{self.underlyingValue:,.2f}")

        # --- 2. initialise quoted price once ----------------------------------
        if not hasattr(self, "quoted"):
            self.quoted = ev

        # --- 3. volatility that decays as √(T/T₀) -----------------------------
        T = max(0, GAMETIME - self.time)
        sigma = max(SIGMA_FLOOR, SIGMA0 * math.sqrt(T / GAMETIME))

        # --- 4. OU one‑step update -------------------------------------------
        noise   = random.gauss(0, sigma)
        self.quoted += K_REVERT * (ev - self.quoted) + noise
        self.quoted = max(0, self.quoted)           # no negative prices
        
        self.underlyingValue = self.quoted
        # --- 5. push into series & UI ----------------------------------------
        self.series_x.append(self.time)
        self.series_y.append(self.quoted)
        self.underlyingInfoLabel.setText(f"{self.quoted:,.2f}")

        WINDOW = 30

        if len(self.series_x) > WINDOW:
            self.series_x = self.series_x[-WINDOW:]
            self.series_y = self.series_y[-WINDOW:]

        self.line.set_data(self.series_x, self.series_y)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw_idle()
    
    def stop(self):
        self.timer.stop()


class TimeInfo(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedSize(WIDTH//2.5 - MARGIN, HEIGHT//3 - MARGIN)
        self.setFrameShape(QFrame.StyledPanel)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.time = 0

        self.timeLabel = QLabel()
        self.timeLabel.setStyleSheet("font-size: 64px;")
        self.timeLabel.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.timeLabel)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateTime)
        self.timer.start(1000)

        self.updateTime()
    
    def stop(self):
        self.timer.stop()

    
    def updateTime(self):
        self.time += 1
        seconds = self.time % 60
        minutes = self.time // 60
        if seconds < 10 and minutes < 10:
            self.timeLabel.setText(f"0{minutes} : 0{seconds}")
        elif seconds < 10:
            self.timeLabel.setText(f"{minutes} : 0{seconds}")
        elif minutes < 10:
            self.timeLabel.setText(f"0{minutes} : {seconds}")
        else:
            self.timeLabel.setText(f"{minutes} : {seconds}")
        
        signals.timeChanged.emit(self.time)

        if self.time == GAMETIME:
            signals.gameOver.emit()
            

class PlayerInfo(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedSize(WIDTH//2.5 - MARGIN, HEIGHT//2 - MARGIN)
        self.setFrameShape(QFrame.StyledPanel)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        
        # Building info panel
        self.balanceUI = QLabel("1000")
        self.balanceUI.setFixedSize(200, 200)

        self.layout.addWidget(self.balanceUI)

        signals.balanceChanged.connect(self.updateBalance)

    def updateBalance(self, val):
        self.balanceUI.setText(f"{val}")


class Fruits(QObject):
    def __init__(self):
        super().__init__()
        self.oranges1 = 0
        self.lemons1 = 0
        self.oranges2 = 0
        self.lemons2 = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateFruit)
        self.timer.start(1000)

        self.updateFruit()
    
    def updateFruit(self):
        if O1PROB > random.random():
            self.oranges1 += 1
        if L1PROB > random.random():
            self.lemons1 += 1
        if O2PROB > random.random():
            self.oranges2 += 1
        if L2PROB > random.random():
            self.lemons2 += 1
        signals.fruitChanges.emit(self.oranges1, self.lemons1, self.oranges2, self.lemons2)

    def stop(self):
        self.timer.stop()
    
    def fruitValues(self):
        return (self.oranges1, self.lemons1, self.oranges2, self.lemons2)

class FruitInfo(QFrame):
    def __init__(self):
        super().__init__()

        self.fruits = Fruits()

        self.setFixedSize(WIDTH//2.5 - MARGIN, HEIGHT//3 - MARGIN)
        self.setFrameShape(QFrame.StyledPanel)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        
        # Building info panel
        self.teamsLayout = QHBoxLayout()
        self.team1Oranges = QLabel("Oranges: ")
        self.team1Lemons = QLabel("Lemons: ")
        self.team2Oranges = QLabel("Oranges: ")
        self.team2Lemons = QLabel("Lemons: ")
        self.team1Oranges.setStyleSheet("font-size: 20px;")
        self.team1Lemons.setStyleSheet("font-size: 20px;")
        self.team2Oranges.setStyleSheet("font-size: 20px;")
        self.team2Lemons.setStyleSheet("font-size: 20px;")
        self.team1Oranges.setAlignment(Qt.AlignCenter)
        self.team1Lemons.setAlignment(Qt.AlignCenter)
        self.team2Oranges.setAlignment(Qt.AlignCenter)
        self.team2Lemons.setAlignment(Qt.AlignCenter)
        self.teamsLayout.addWidget(self.team1Oranges)
        self.teamsLayout.addWidget(self.team1Lemons)
        self.teamsLayout.addWidget(self.team2Oranges)
        self.teamsLayout.addWidget(self.team2Lemons)
        
        self.bannerLayout = QHBoxLayout()
        self.team1Label = QLabel("Team 1")
        self.team2Label = QLabel("Team 2")
        font = self.team1Label.font()
        font.setBold(True)
        font.setPointSize(20)
        self.team1Label.setFont(font)
        self.team2Label.setFont(font)
        self.team1Label.setAlignment(Qt.AlignCenter)
        self.team2Label.setAlignment(Qt.AlignCenter)
        self.bannerLayout.addWidget(self.team1Label)
        self.bannerLayout.addWidget(self.team2Label)

        signals.fruitChanges.connect(self.updateFruitLabels)

        self.layout.addLayout(self.bannerLayout)
        self.layout.addLayout(self.teamsLayout)
    
    def updateFruitLabels(self, o1, l1, o2, l2):
        self.team1Oranges.setText(f"Oranges: {o1}")
        self.team1Lemons.setText(f"Lemons: {l1}")
        self.team2Oranges.setText(f"Oranges: {o2}")
        self.team2Lemons.setText(f"Lemons: {l2}")


class TradeSection(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedSize(WIDTH//2.5 - MARGIN, HEIGHT//1.5 - MARGIN)
        self.setFrameShape(QFrame.StyledPanel)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        
        scrollContent = QWidget()
        self.scrollLayout = QVBoxLayout(scrollContent)
        scrollArea = QScrollArea()
        scrollArea.setWidgetResizable(True)

        scrollArea.setWidget(scrollContent)
        self.layout.addWidget(scrollArea)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.addTrade)
        self.scheduleTrade()

        self.o1 = 0
        self.o2 = 0
        self.l1 = 0
        self.l2 = 0
        self.time = 0

        signals.timeChanged.connect(self.updateTime)
        signals.fruitChanges.connect(self.updateFruits)
    
    def updateTime(self, time):
        self.time = time

    def updateFruits(self, o1, l1, o2, l2):
        self.o1 = o1
        self.l1 = l1
        self.o2 = o2
        self.l2 = l2

    def scheduleTrade(self):
        delay = max((GAMETIME*1000)//15, (GAMETIME*1000)//15 + random.randint(-4000, 4000))
        self.timer.start(delay)

    def addTrade(self):
        for _ in range(random.randint(1,3)):
            wrapper = QWidget()
            hbox = QHBoxLayout()
            hbox.setContentsMargins(0, 0, 0, 0)
            hbox.setAlignment(Qt.AlignHCenter)
            trade = TradeUI((self.time, self.o1, self.l1, self.o2, self.l2))
            hbox.addWidget(trade)
            wrapper.setLayout(hbox)
            self.scrollLayout.addWidget(wrapper)
        self.scheduleTrade()
    
    def stop(self):
        self.timer.stop()

    
class Trade:
    def __init__(self, func, values, text):
        time, o1, l1, o2, l2 = values
        self.text = text
        self.func = func
        T = GAMETIME - time
        o1 += T * O1PROB_NOISY
        l1 += T * L1PROB_NOISY
        o2 += T * O2PROB_NOISY
        l2 += T * L2PROB_NOISY
        self.value = int(func(o1, l1, o2, l2))
        self.side = Side.IGNORED


class TradeUI(QFrame):
    def __init__(self, values):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameStyle(QFrame.Box | QFrame.Shadow.Raised)
        self.setFixedSize(450, 140)

        tradeTypes = [
            ("2 ^ (team 1 oranges)", lambda o1, l1, o2, l2: 2**o1),
            ("2 ^ (team 2 oranges)", lambda o1, l1, o2, l2: 2**o2),
            ("2 ^ (team 1 lemons)", lambda o1, l1, o2, l2: 2**l1),
            ("2 ^ (team 2 lemons)", lambda o1, l1, o2, l2: 2**l2),

            ("team 1 oranges + team 2 oranges", lambda o1, l1, o2, l2: o1 + o2),
            ("team 1 oranges - team 2 oranges", lambda o1, l1, o2, l2: o1 - o2),
            ("team 2 oranges - team 1 oranges", lambda o1, l1, o2, l2: o2 - o1),
            ("team 1 oranges * team 2 oranges", lambda o1, l1, o2, l2: o1 * o2),

            ("team 1 lemons + team 2 lemons", lambda o1, l1, o2, l2: l1 + l2),
            ("team 1 lemons * team 2 lemons", lambda o1, l1, o2, l2: l1 * l2),
            ("team 1 lemons - team 2 lemons", lambda o1, l1, o2, l2: l1 - l2),
            ("team 2 lemons - team 1 lemons", lambda o1, l1, o2, l2: l2 - l1),

            ("team 1 oranges + team 2 lemons", lambda o1, l1, o2, l2: o1 + l2),
            ("team 1 oranges - team 2 lemons", lambda o1, l1, o2, l2: o1 - l2),
            ("team 2 lemons - team 1 oranges", lambda o1, l1, o2, l2: l2 - o1),
            ("team 1 oranges * team 2 lemons", lambda o1, l1, o2, l2: o1 * l2),
   
            ("team 2 oranges + team 1 lemons", lambda o1, l1, o2, l2: o2 + l1),
            ("team 2 oranges - team 1 lemons", lambda o1, l1, o2, l2: o2 - l1),
            ("team 1 lemons - team 2 oranges", lambda o1, l1, o2, l2: l1 - o2),
            ("team 2 oranges * team 1 lemons", lambda o1, l1, o2, l2: o2 * l1),
        ]

        self.timeLimit = int(random.choice([max(GAMETIME//45, 10),max(GAMETIME//30, 10), max(GAMETIME//7.5, 10), max(GAMETIME//15, 10)]))
        self.tradeText, func = random.choice(tradeTypes)

        self.trade = Trade(func, values, self.tradeText)

        self.price = self.trade.value

        # UI
        self.tradeInfo = QLabel(f"{self.tradeText} @ {self.price}\nexpires in {self.timeLimit}")
        self.tradeInfo.setAlignment(Qt.AlignCenter)
        self.tradeInfo.setStyleSheet("font-size: 20px;")

        self.buttonLayout = QHBoxLayout()
        self.buyButton = QPushButton("Buy", self, clicked=self.buy)
        self.buyButton.setFixedSize(100,30)
        self.sellButton = QPushButton("Sell", self, clicked=self.sell)
        self.sellButton.setFixedSize(100,30)

        self.buttonLayout.addWidget(self.buyButton)
        self.buttonLayout.addWidget(self.sellButton)

        self.layout.addWidget(self.tradeInfo)
        self.layout.addLayout(self.buttonLayout)

        # timer related
        self.time = 0
        signals.timeChanged.connect(self.updateTime)

    def updateTime(self):
        self.time += 1
        if self.time >= self.timeLimit - 10:
            self.tradeInfo.setStyleSheet("color: #ED2939; font-size: 20px;")
        self.tradeInfo.setText(f"{self.tradeText} @ {self.price}\nexpires in {self.timeLimit - self.time}")
        if self.time >= self.timeLimit:
            self.setVisible(False)
        
    def buy(self):
        self.trade.side = Side.BUY
        signals.traded.emit(self.trade)
        self.setVisible(False)

    def sell(self):
        self.trade.side = Side.SELL
        signals.traded.emit(self.trade)
        self.setVisible(False)

class MarketHistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Market History")
        self.setFixedSize(550, 415)
        layout = QVBoxLayout(self)

        # -- table 5 columns: Run, T1 O, T1 L, T2 O, T2 L --------------
        table = QTableWidget(11, 5)
        table.verticalHeader().setVisible(False)
        table.setHorizontalHeaderLabels(
            ["Run", "team 1 oranges", "team 1 lemons", "team 2 oranges", "team 2 lemons"]
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        o1results = []
        l1results = []
        o2results = []
        l2results = []
        for i in range(10):
            o1, l1, o2, l2 = simulate_final_counts()
            o1results.append(o1)
            l1results.append(l1)
            o2results.append(o2)
            l2results.append(l2)
            tableEntry1 = QTableWidgetItem(str(i+1))
            tableEntry1.setTextAlignment(Qt.AlignCenter)
            tableEntry2 = QTableWidgetItem(QTableWidgetItem(str(o1)))
            tableEntry2.setTextAlignment(Qt.AlignCenter)
            tableEntry3 = QTableWidgetItem(QTableWidgetItem(str(l1)))
            tableEntry3.setTextAlignment(Qt.AlignCenter)
            tableEntry4 = QTableWidgetItem(QTableWidgetItem(str(o2)))
            tableEntry4.setTextAlignment(Qt.AlignCenter)
            tableEntry5 = QTableWidgetItem(QTableWidgetItem(str(l2)))
            tableEntry5.setTextAlignment(Qt.AlignCenter)
            table.setItem(i, 0, tableEntry1)
            table.setItem(i, 1, tableEntry2)
            table.setItem(i, 2, tableEntry3)
            table.setItem(i, 3, tableEntry4)
            table.setItem(i, 4, tableEntry5)

        label_item = QTableWidgetItem("Total")
        label_item.setTextAlignment(Qt.AlignCenter)
        label_item.setFlags(Qt.ItemIsEnabled)
        table.setItem(10, 0, label_item)

        # Total values
        totals = [sum(o1results), sum(l1results), sum(o2results), sum(l2results)]
        for col in range(4):
            item = QTableWidgetItem(str(totals[col]))
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.ItemIsEnabled)
            table.setItem(10, col+1, item)

        layout.addWidget(table)

        # -- buttons ----------------------------------------------------
        btn_box = QHBoxLayout()
        start_btn = QPushButton("Start Trading")
        start_btn.setFixedSize(100, 30)
        btn_box.addStretch()
        btn_box.addWidget(start_btn)
        btn_box.addStretch()
        layout.addLayout(btn_box)

        start_btn.clicked.connect(self.accept)

class Window(QWidget):
    def __init__(self):
        self.player = Player()  
        super().__init__()
        self.setWindowTitle("Fruit Market Making")
        self.setFixedSize(WIDTH,HEIGHT)

        self.layout = QGridLayout()
        self.setLayout(self.layout)

        self.tradeSection = TradeSection()
        self.trackerInfo = TrackerInfo()
        self.timeInfo = TimeInfo()
        self.fruitInfo = FruitInfo()
        self.tradeHistory = TradeHistory()

        self.layout.addWidget(self.tradeSection, 0, 0)
        self.layout.addWidget(self.trackerInfo, 0, 1)
        self.layout.addWidget(self.timeInfo, 1, 0)
        self.layout.addWidget(self.fruitInfo, 1, 1)
        self.layout.addWidget(self.tradeHistory, 0, 2, 2, 1)

        signals.gameOver.connect(self.stopGame)
    
    def stopGame(self):
        self.tradeSection.stop()
        self.trackerInfo.stop()
        self.timeInfo.stop()
        self.fruitInfo.fruits.stop()

        score = self.player.calculateScore(self.fruitInfo.fruits.fruitValues())
        dialog = QDialog(self)
        dialog.setWindowTitle("Profit and Loss")
        dialog.setFixedSize(200, 200)

        layout = QVBoxLayout(dialog)

        scoreLabel = QLabel(f"{score:,.2f}")
        if score > 0:
            scoreLabel.setStyleSheet("color: #80EF80; font-size: 22px;")
        elif score < 0:
            scoreLabel.setStyleSheet("color: #FF6961; font-size: 22px;")
        else:
            scoreLabel.setStyleSheet("color: #FFFFFF; font-size: 22px;")
        scoreLabel.setAlignment(Qt.AlignCenter)

        buttonLayout = QHBoxLayout()
        quitButton = QPushButton("Quit")
        quitButton.setStyleSheet("font-size: 18px; padding: 6px 16px;")
        buttonLayout.addStretch()
        buttonLayout.addWidget(quitButton)
        buttonLayout.addStretch()

        layout.addWidget(scoreLabel)
        layout.addLayout(buttonLayout)

        quitButton.clicked.connect(dialog.reject)

        if dialog.exec() == QDialog.Rejected:
            QApplication.quit()
    
    def restartGame(self):
        print("Restarting...")
        os.execl(sys.executable, sys.executable, *sys.argv)

class Player(QObject):
    def __init__(self):
        super().__init__()
        self.balance = 0.0
        self.position = 0
        self.trades: Trade = []
        signals.traded.connect(self.addTrade)
        signals.buy.connect(self.buy)
        signals.sell.connect(self.sell)

    def calculateScore(self, fruitValues):
        o1, l1, o2, l2 = fruitValues
        result = self.balance

        for trade in self.trades:
            if trade.side == Side.SELL:
                result += trade.value
                result -= trade.func(o1, l1, o2, l2)
            elif trade.side == Side.BUY:
                result -= trade.value
                result += trade.func(o1, l1, o2, l2)
        
        market_fair_value = (o1 + o2) * (l1 + l2)
        result +=  float(market_fair_value) *  float(self.position)

        return result
    
    def updateBalance(self, val):
        self.balance += val
        signals.balanceChanged.emit(self.balance)
    
    def addTrade(self, trade):
        self.trades.append(trade)

    def sell(self, val):
        self.position -= 1
        self.updateBalance(val)
    
    def buy(self, val):
        self.position += 1
        self.updateBalance(-val)

if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        base_path = sys._MEIPASS
    else:
        # Running in normal Python environment
        base_path = os.path.abspath(".")

    icon_path = os.path.join(base_path, "lemon.ico")
    app = QApplication()
    app.setWindowIcon(QIcon(icon_path))
    history = MarketHistoryDialog()
    if history.exec() != QDialog.Accepted:
        sys.exit(0)   
    window = Window()
    window.show()
    sys.exit(app.exec())