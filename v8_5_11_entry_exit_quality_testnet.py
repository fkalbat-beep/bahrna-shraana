
import os, time, hmac, hashlib, json, math, csv, re
from urllib.parse import urlencode
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_DOWN
import xml.etree.ElementTree as ET

import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ---------------------------
# ENVIRONMENT / ENDPOINTS
# ---------------------------
MARKET = "https://data-api.binance.vision"
TESTNET = "https://testnet.binance.vision"

KEY = os.getenv("BINANCE_TESTNET_API_KEY", "")
SECRET = os.getenv("BINANCE_TESTNET_API_SECRET", "")
ALLOW = os.getenv("ALLOW_TESTNET_MATCHING_ENGINE", "false").lower() == "true"

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

M = requests.Session()
T = requests.Session()
OFFSET = 0

# ---------------------------
# V8.5 PRZ CLEAN INTRADAY CONFIG — isolated state / 3m trigger / 5m setup
# ---------------------------
CFG = {
    "allocation_pct": 0.40,
    "daily_loss_stop_pct": -0.01,
    "daily_profit_cap_pct": None,
    "risk_A": 0.003,
    "risk_B": 0.0015,
    "max_portfolio_open_risk_pct": 0.0090,  # V8.2.1: 0.90% aggregate open-risk; NO fixed position count
    "max_single_position_allocation_pct": 0.20,
    "scan_sec": 20,  # short pause after each completed radar/deep cycle
    "radar_top_n": 56,
    "radar_rotation_n": 20,
    "radar_workers": 18,
    "deep_workers": 10,

    "min_quote_vol": 25_000_000,
    "min_day_range": 0.035,
    "max_day_range": 0.25,
    "max_spread_pct": 0.0015,
    "min_atr_pct": 0.003,
    "max_atr_pct": 0.04,

    "atr_mult": 1.35,

    # V8.4 signal architecture
    # 1H/15m = context only; 5m = setup; 3m = execution trigger.
    "leading_min": 62,
    "timing_min": 64,
    "confirmation_min": 52,
    "total_A": 86,
    "total_B": 78,
    "max_extension_atr_5m": 1.35,   # reject late/chasing entries
    "max_extension_pct_5m": 0.018,  # hard late-entry guard
    "min_rvol_3m": 1.05,
    "min_rvol_5m": 1.10,

    # V8.5 PRZ / entry engine
    "entry_timeframes": ["1m", "3m", "5m"],
    "prz_tolerance_atr": 0.55,
    "max_prz_chase_atr": 0.65,
    "soft_late_prz_atr": 0.95,
    "hard_late_prz_atr": 1.60,
    "soft_late_vwap_atr": 1.05,
    "hard_late_vwap_atr": 1.75,
    "soft_late_rsi_1m": 82.0,
    "hard_late_rsi_1m": 88.0,
    "soft_late_rsi_3m": 80.0,
    "hard_late_rsi_3m": 86.0,
    "momentum_recheck_min_score": 58,
    "momentum_recheck_min_rvol_1m": 1.40,
    "momentum_recheck_min_rvol_3m": 1.25,
    "momentum_recheck_min_accel_pct": 0.15,
    "retest_tolerance_atr": 0.35,
    "min_trigger_score": 58,
    "min_harmonic_confidence": 0.72,
    "stoch_rsi_low": 0.18,
    "stoch_rsi_high": 0.82,
    "tp1_pct": 0.20,
    "tp2_pct": 0.35,
    "tp3_pct": 0.45,
    "structural_stop_atr_buffer": 0.30,
    "tp1_move_stop_mode": "STRUCTURE",

    # Multi-target plan
    "tp1_r": 1.00,
    "tp2_r": 1.70,
    "tp3_r": 2.50,

    # V8.3 adaptive runner: activates after TP2; software trailing exit
    "trailing_min_pct": 0.004,
    "trailing_max_pct": 0.006,
    "trailing_atr_factor": 0.80,

    # After TP1
    "tp1_decision_timeout_sec": 120,
    "tp1_default_action": "CONTINUE",  # CONTINUE or CLOSE
    "breakeven_buffer_pct": 0.001,     # +0.10% above entry

    # Monthly information only; never increases risk to "catch up".
    "monthly_target_multiple_low": 2.0,
    "monthly_target_multiple_high": 3.0,

    "state": "/data/v8_5_11_state.json",
    "trades": "/data/v8_5_11_trades.csv",
    "daily": "/data/v8_5_11_daily.csv",
    "scanner": "/data/v8_5_11_scanner.csv",
    "chart_dir": "/data/v8_5_11_charts",
    "audit": "/data/v8_5_11_audit.csv",
    "post_exit_minutes": [5,15,30,60],
}

ENGINE_ID = "V8.5.11-ENTRY-EXIT-QUALITY-20260903-ISO1-PERSIST"

STABLE = {"USDC","FDUSD","TUSD","USDP","DAI","EUR","AEUR","TRY","BRL","GBP"}
LEV = ("UP","DOWN","BULL","BEAR")

NEWS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://decrypt.co/feed",
]

# ---------------------------
# HELPERS
# ---------------------------
def utcday():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def iso():
    return datetime.now(timezone.utc).isoformat()

def uae_now():
    return datetime.now(timezone.utc) + timedelta(hours=4)

def uae_day():
    return uae_now().strftime("%Y-%m-%d")

def mg(path, params=None):
    r = M.get(MARKET + path, params=params or {}, timeout=20)
    r.raise_for_status()
    return r.json()

def tg(path, params=None):
    r = T.get(TESTNET + path, params=params or {}, timeout=20)
    r.raise_for_status()
    return r.json()

def sync():
    global OFFSET
    OFFSET = int(tg("/api/v3/time")["serverTime"]) - int(time.time() * 1000)

def signed(method, path, params=None):
    if not KEY or not SECRET:
        raise RuntimeError("Testnet keys not set.")
    sync()
    p = dict(params or {})
    p["timestamp"] = int(time.time() * 1000) + OFFSET
    p["recvWindow"] = 10000
    qs = urlencode(p)
    sig = hmac.new(SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()
    r = T.request(
        method,
        TESTNET + path + "?" + qs + "&signature=" + sig,
        headers={"X-MBX-APIKEY": KEY},
        timeout=20,
    )
    if not r.ok:
        raise RuntimeError(f"{r.status_code}: {r.text}")
    return r.json()

def telegram(msg, reply_markup=None):
    try:
        if not TG_TOKEN or not TG_CHAT:
            return False
        data = {"chat_id": TG_CHAT, "text": msg}
        if reply_markup is not None:
            data["reply_markup"] = json.dumps(reply_markup)
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data=data,
            timeout=15,
        )
        return bool(r.ok and r.json().get("ok"))
    except Exception as ex:
        print("[TELEGRAM WARN]", str(ex)[:160])
        return False

def telegram_photo(path, caption=""):
    try:
        if not TG_TOKEN or not TG_CHAT:
            return False
        with open(path, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto",
                data={"chat_id": TG_CHAT, "caption": caption[:1024]},
                files={"photo": f},
                timeout=30,
            )
        return bool(r.ok and r.json().get("ok"))
    except Exception as ex:
        print("[TELEGRAM PHOTO WARN]", str(ex)[:160])
        return False

def telegram_updates(offset=None, timeout=1):
    if not TG_TOKEN:
        return []
    p = {"timeout": timeout}
    if offset is not None:
        p["offset"] = offset
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates",
            params=p,
            timeout=timeout + 5,
        )
        if r.ok:
            return r.json().get("result", [])
    except Exception as ex:
        print("[TELEGRAM UPDATE WARN]", str(ex)[:120])
    return []

def answer_callback(callback_id, text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/answerCallbackQuery",
            data={"callback_query_id": callback_id, "text": text},
            timeout=10,
        )
    except Exception:
        pass

def account():
    return signed("GET", "/api/v3/account")

def bal(asset):
    for b in account().get("balances", []):
        if b["asset"] == asset:
            return float(b["free"])
    return 0.0

def symbol_info(sym):
    return tg("/api/v3/exchangeInfo", {"symbol": sym})["symbols"][0]

def fget(sym, typ):
    for f in symbol_info(sym)["filters"]:
        if f["filterType"] == typ:
            return f
    return {}

def floor_step(v, s):
    return math.floor(float(v) / float(s)) * float(s)

def tick_floor(v, t):
    return math.floor(float(v) / float(t)) * float(t)

def fmt(v):
    return f"{float(v):.12f}".rstrip("0").rstrip(".")

def quote_precision(sym):
    info = symbol_info(sym)
    p = info.get("quoteAssetPrecision", info.get("quotePrecision", 8))
    try:
        return int(p)
    except Exception:
        return 8

def normalize_quote_amount(sym, amount):
    precision = quote_precision(sym)
    quantum = Decimal("1").scaleb(-precision)
    value = Decimal(str(amount)).quantize(quantum, rounding=ROUND_DOWN)
    return format(value, "f")

# ---------------------------
# MULTI-BOT ISOLATION
# ---------------------------
BOT_ORDER_PREFIX = "V85"

def _client_id(kind):
    # Binance clientOrderId max length is limited; keep it compact and unique.
    return f"{BOT_ORDER_PREFIX}_{kind}_{int(time.time()*1000)%10**12}"[:36]

def open_orders(sym=None):
    params = {"symbol": sym} if sym else {}
    return signed("GET", "/api/v3/openOrders", params)

def symbol_locked_by_account(sym):
    """
    Shared-account safety gate. If ANY open order already exists for this symbol
    on the Binance Testnet account, this bot will not open a new position.
    This prevents V8.4/V8.5/Swing overlap even before every bot is fully tagged.
    """
    try:
        orders = open_orders(sym)
        if orders:
            owners = sorted(set(str(o.get("clientOrderId", ""))[:3] or "UNK" for o in orders))
            print(f"[ISOLATION LOCK] {sym} blocked: {len(orders)} account open order(s), owners={owners}")
            return True
    except Exception as ex:
        # Fail closed: if we cannot verify isolation, do not create a new position.
        print(f"[ISOLATION CHECK ERROR] {sym}: {str(ex)[:140]}")
        return True
    return False

# ---------------------------
# BINANCE ORDERS
# ---------------------------
def buy(sym, quote):
    if not ALLOW:
        raise RuntimeError("Execution locked.")
    return signed("POST", "/api/v3/order", {
        "symbol": sym,
        "side": "BUY",
        "type": "MARKET",
        "quoteOrderQty": normalize_quote_amount(sym, quote),
        "newOrderRespType": "FULL",
        "newClientOrderId": _client_id("BUY"),
    })

def market_sell(sym, qty):
    if not ALLOW:
        raise RuntimeError("Execution locked.")
    lot = fget(sym, "LOT_SIZE")
    q = floor_step(qty, lot.get("stepSize", "0.00000001"))
    if q <= 0:
        return None
    return signed("POST", "/api/v3/order", {
        "symbol": sym,
        "side": "SELL",
        "type": "MARKET",
        "quantity": fmt(q),
        "newOrderRespType": "FULL",
        "newClientOrderId": _client_id("SELL"),
    })

def place_oco(sym, qty, tp, stop):
    lot = fget(sym, "LOT_SIZE")
    pf = fget(sym, "PRICE_FILTER")
    q = floor_step(qty, lot.get("stepSize", "0.00000001"))
    tick = float(pf.get("tickSize", "0.00000001"))
    tp = tick_floor(tp, tick)
    stop = tick_floor(stop, tick)
    stop_limit = tick_floor(stop * (1 - 0.002), tick)

    last = float(tg("/api/v3/ticker/price", {"symbol": sym})["price"])
    if not (tp > last > stop):
        raise RuntimeError(f"OCO price rule failed {tp}>{last}>{stop}")

    return signed("POST", "/api/v3/orderList/oco", {
        "symbol": sym,
        "side": "SELL",
        "quantity": fmt(q),
        "aboveType": "LIMIT_MAKER",
        "abovePrice": fmt(tp),
        "belowType": "STOP_LOSS_LIMIT",
        "belowStopPrice": fmt(stop),
        "belowPrice": fmt(stop_limit),
        "belowTimeInForce": "GTC",
        "newOrderRespType": "RESULT",
        "listClientOrderId": _client_id("OCO"),
        "aboveClientOrderId": _client_id("TP"),
        "belowClientOrderId": _client_id("SL"),
    })

def order_list(list_id):
    return signed("GET", "/api/v3/orderList", {"orderListId": list_id})

def order(sym, oid):
    return signed("GET", "/api/v3/order", {"symbol": sym, "orderId": oid})

def cancel_oco(sym, list_id):
    return signed("DELETE", "/api/v3/orderList", {
        "symbol": sym,
        "orderListId": list_id,
    })

def oco_filled_quote(sym, list_id):
    ol = order_list(list_id)
    total = 0.0
    filled_qty = 0.0
    for o in ol.get("orders", []):
        q = order(sym, o["orderId"])
        if q.get("status") == "FILLED":
            total += float(q.get("cummulativeQuoteQty", 0))
            filled_qty += float(q.get("executedQty", 0))
    return total, filled_qty, ol.get("listOrderStatus")

# ---------------------------
# INDICATORS / SIGNALS
# ---------------------------
def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()

def rsi(s, n=14):
    x = s.diff()
    u = x.clip(lower=0)
    dn = -x.clip(upper=0)
    ag = u.ewm(alpha=1/n, adjust=False).mean()
    al = dn.ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + ag / al.replace(0, np.nan))

def atr(d, n=14):
    pc = d.c.shift(1)
    tr = pd.concat(
        [d.h-d.l, (d.h-pc).abs(), (d.l-pc).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def stoch_rsi_series(rsi_series, n=14, k=3, d=3):
    """Stochastic RSI in 0..100 using closed-candle data."""
    lo = rsi_series.rolling(n).min()
    hi = rsi_series.rolling(n).max()
    raw = 100.0 * (rsi_series - lo) / (hi - lo).replace(0, np.nan)
    sk = raw.rolling(k).mean()
    sd = sk.rolling(d).mean()
    return sk, sd


def _candle_reversal_bidirectional(d):
    """Broad reversal library. Returns bullish_score, bearish_score, bullish_names, bearish_names."""
    if len(d) < 6:
        return 0, 0, [], []
    a = d.iloc[-4]
    b = d.iloc[-3]
    c = d.iloc[-2]  # last CLOSED candle
    bull = 0; bear = 0; bn=[]; sn=[]
    body = abs(c.c-c.o); rng=max(c.h-c.l,1e-12)
    lower=min(c.o,c.c)-c.l; upper=c.h-max(c.o,c.c)
    prev_body=abs(b.c-b.o); prev_rng=max(b.h-b.l,1e-12)

    # Engulfing
    if c.c>c.o and b.c<b.o and c.o<=b.c and c.c>=b.o:
        bull += 16; bn.append('Bullish Engulfing')
    if c.c<c.o and b.c>b.o and c.o>=b.c and c.c<=b.o:
        bear += 16; sn.append('Bearish Engulfing')
    # Hammer / hanging man / shooting star style rejection
    if lower >= max(body*1.8, rng*0.35) and upper <= rng*0.25:
        if c.c >= c.o: bull += 13; bn.append('Hammer / Bullish Pin')
        else: bull += 9; bn.append('Lower-wick rejection')
    if upper >= max(body*1.8, rng*0.35) and lower <= rng*0.25:
        if c.c <= c.o: bear += 13; sn.append('Shooting Star / Bearish Pin')
        else: bear += 9; sn.append('Upper-wick rejection')
    # Morning / evening star approximations
    if a.c<a.o and abs(b.c-b.o) <= 0.45*max(abs(a.c-a.o),1e-12) and c.c>c.o and c.c >= (a.o+a.c)/2:
        bull += 15; bn.append('Morning Star')
    if a.c>a.o and abs(b.c-b.o) <= 0.45*max(abs(a.c-a.o),1e-12) and c.c<c.o and c.c <= (a.o+a.c)/2:
        bear += 15; sn.append('Evening Star')
    # Piercing / dark cloud
    if b.c<b.o and c.c>c.o and c.o<b.c and c.c>(b.o+b.c)/2 and c.c<b.o:
        bull += 11; bn.append('Piercing Line')
    if b.c>b.o and c.c<c.o and c.o>b.c and c.c<(b.o+b.c)/2 and c.c>b.o:
        bear += 11; sn.append('Dark Cloud Cover')
    # Tweezer bottom/top approximation
    atrv=max(float(c.atr) if pd.notna(c.atr) else rng, 1e-12)
    if abs(float(b.l)-float(c.l)) <= 0.12*atrv and b.c<b.o and c.c>c.o:
        bull += 9; bn.append('Tweezer Bottom')
    if abs(float(b.h)-float(c.h)) <= 0.12*atrv and b.c>b.o and c.c<c.o:
        bear += 9; sn.append('Tweezer Top')
    # Three soldiers / crows approximation
    last3=d.iloc[-4:-1]
    if len(last3)==3 and all(last3.c>last3.o) and all(last3.c.diff().dropna()>0):
        bull += 10; bn.append('Three White Soldiers')
    if len(last3)==3 and all(last3.c<last3.o) and all(last3.c.diff().dropna()<0):
        bear += 10; sn.append('Three Black Crows')
    return min(30,bull), min(30,bear), bn, sn


def _bb_position(c):
    lo=float(c.bb_lo); mid=float(c.bb_mid); up=float(c.bb_up); px=float(c.c)
    width=max(up-lo,1e-12)
    return max(-0.25,min(1.25,(px-lo)/width)), lo, mid, up


def _ichimoku_context(d):
    c=d.iloc[-2]
    vals=[getattr(c,x,np.nan) for x in ('ichi_a','ichi_b','tenkan','kijun')]
    if any(pd.isna(v) for v in vals):
        return 0, 'Ichimoku unavailable'
    a,b,t,k=map(float,vals); px=float(c.c)
    top=max(a,b); bot=min(a,b)
    if px>top and t>=k: return 8, 'Above cloud / bullish context'
    if px<bot and t<k: return -8, 'Below cloud / bearish context'
    return 0, 'Inside cloud / neutral context'


def _weighted_entry_confluence(d1m,d3,d5,d15,d1, harmonic_score=0, base_leading=0, base_timing=0, base_confirm=0):
    """Weighted evidence model. Only extreme chase/risk conditions remain hard blocks."""
    c1=d1m.iloc[-2]; c3=d3.iloc[-2]; c5=d5.iloc[-2]; c15=d15.iloc[-2]
    score=0.0; reasons=[]

    # RSI: oversold recovery is strongest; neutral rising remains supportive.
    r1=float(c1.rsi); r3=float(c3.rsi); r5=float(c5.rsi); r15=float(c15.rsi)
    p1=float(d1m.iloc[-3].rsi); p3=float(d3.iloc[-3].rsi)
    low1=float(d1m.rsi.iloc[-10:-2].min()); low3=float(d3.rsi.iloc[-8:-2].min())
    if (low1<=32 or low3<=35) and (r1>p1 or r3>p3): score+=18; reasons.append('RSI oversold recovery +18')
    elif r1>p1 and r3>p3 and r3<68: score+=9; reasons.append('RSI rising +9')
    if r5>=72 or r15>=72: score-=8; reasons.append('Higher-TF RSI extended -8')

    # Stoch RSI: fast timing only, never sole trigger.
    sk1=float(c1.stoch_k) if pd.notna(c1.stoch_k) else 50; sd1=float(c1.stoch_d) if pd.notna(c1.stoch_d) else 50
    sk3=float(c3.stoch_k) if pd.notna(c3.stoch_k) else 50; sd3=float(c3.stoch_d) if pd.notna(c3.stoch_d) else 50
    prevk1=float(d1m.iloc[-3].stoch_k) if pd.notna(d1m.iloc[-3].stoch_k) else sk1
    prevk3=float(d3.iloc[-3].stoch_k) if pd.notna(d3.iloc[-3].stoch_k) else sk3
    if (prevk1<=20 and sk1>prevk1 and sk1>=sd1) or (prevk3<=20 and sk3>prevk3 and sk3>=sd3):
        score+=15; reasons.append('StochRSI exits oversold +15')
    elif sk1>sd1 and sk3>sd3 and sk1<80 and sk3<80:
        score+=7; reasons.append('StochRSI constructive +7')
    if sk3>=92 and r3>=72: score-=10; reasons.append('StochRSI/RSI overheated -10')

    # Broad candles, both directions.
    b3,s3,bn3,sn3=_candle_reversal_bidirectional(d3)
    b5,s5,bn5,sn5=_candle_reversal_bidirectional(d5)
    candle_net=(b3+0.6*b5)-(s3+0.6*s5)
    score += max(-18,min(18,candle_net))
    if bn3 or bn5: reasons.append('Bullish reversal candles: '+', '.join((bn3+bn5)[:3]))
    if sn3 or sn5: reasons.append('Bearish reversal candles: '+', '.join((sn3+sn5)[:3]))

    # Bollinger location: lower-band recovery -> mid -> upper. Context, not a trigger.
    pos3,lo3,mid3,up3=_bb_position(c3); pos5,lo5,mid5,up5=_bb_position(c5)
    if pos3<=0.18 and float(c3.c)>float(d3.iloc[-3].c): score+=10; reasons.append('Lower Bollinger recovery +10')
    elif float(c3.c)>=mid3 and pos3<0.88: score+=6; reasons.append('Above Bollinger midline +6')
    if pos5>=0.95 and r5>=70: score-=8; reasons.append('Upper Bollinger + high RSI -8')

    # Relative volume / acceleration.
    rv3=float(c3.rvol) if pd.notna(c3.rvol) else 0; rv5=float(c5.rvol) if pd.notna(c5.rvol) else 0
    if rv3>=1.5: score+=7; reasons.append(f'3m RVOL {rv3:.2f}x +7')
    if rv5>=1.3: score+=5; reasons.append(f'5m RVOL {rv5:.2f}x +5')

    # Ichimoku = context only.
    ichi15,ir15=_ichimoku_context(d15); ichi1,ir1=_ichimoku_context(d1)
    score += 0.6*ichi15 + 0.4*ichi1
    reasons.append(ir15)

    # Preserve legacy intelligence but prevent a single weak group from vetoing the whole trade.
    legacy = 0.22*base_leading + 0.16*base_timing + 0.08*base_confirm + min(8,float(harmonic_score))
    score += legacy

    hard_block = (r1>=88 or r3>=86 or (sk1>=98 and sk3>=95 and r3>=80))
    return {
        'score': round(max(0,min(100,score)),1), 'hard_block':bool(hard_block), 'reasons':reasons,
        'rsi1':r1,'rsi3':r3,'rsi5':r5,'rsi15':r15,'stoch1':sk1,'stoch3':sk3,
        'bb_pos3':round(pos3,3),'bb_pos5':round(pos5,3),'bull_candles':bn3+bn5,'bear_candles':sn3+sn5
    }


def _profit_protection_signal(sym, p):
    """Two-way exit evidence: RSI + StochRSI + Bollinger + bearish candles. Never exits a losing trade."""
    try:
        d1=kl(sym,'1m',100); d3=kl(sym,'3m',100); d5=kl(sym,'5m',100)
        c1=d1.iloc[-2]; c3=d3.iloc[-2]; c5=d5.iloc[-2]
        last=float(c1.c); entry=float(p.get('entry',0))
        if last <= entry: return False, {}, last
        r1=float(c1.rsi); r3=float(c3.rsi); r5=float(c5.rsi)
        k1=float(c1.stoch_k) if pd.notna(c1.stoch_k) else 50; d1s=float(c1.stoch_d) if pd.notna(c1.stoch_d) else 50
        k3=float(c3.stoch_k) if pd.notna(c3.stoch_k) else 50; d3s=float(c3.stoch_d) if pd.notna(c3.stoch_d) else 50
        b3,s3,bn,sn=_candle_reversal_bidirectional(d3)
        pos5,_,mid5,_=_bb_position(c5)
        score=0; why=[]
        if r1>=75 or r3>=75: score+=2; why.append('RSI 70-80 profit zone')
        if (k1>=80 and k1<d1s) or (k3>=80 and k3<d3s): score+=2; why.append('StochRSI rolls down from overbought')
        if pos5>=0.92: score+=1; why.append('Near upper Bollinger')
        if s3>=12: score+=2; why.append('Bearish reversal candle')
        if float(c5.c)<mid5 and r5<60: score+=2; why.append('Lost Bollinger midline / momentum')
        return score>=4, {'score':score,'reasons':why,'rsi1':r1,'rsi3':r3,'stoch1':k1,'stoch3':k3,'bb_pos5':pos5}, last
    except Exception:
        return False, {}, 0.0


def _target_profit(entry, received, filled_qty):
    cost=float(entry)*float(filled_qty)
    pnl=float(received)-cost
    pct=(pnl/cost*100.0) if cost>0 else 0.0
    return pnl,pct

def _target_alert(prefix, sym, p, target_name, target_price, received=0.0, filled_qty=0.0, current_price=None):
    """Compact Telegram milestone requested by Faisal: target, profit cash, profit %. Default is CONTINUE."""
    if filled_qty and received:
        pnl,pct=_target_profit(p.get('entry',0),received,filled_qty)
    else:
        px=float(current_price or target_price)
        qty=sum(float(x.get('qty',0)) for x in p.get('tranches',[]) if x.get('status') in ('OPEN','RUNNER'))
        pnl=(px-float(p.get('entry',0)))*qty
        cost=float(p.get('entry',0))*qty
        pct=(pnl/cost*100.0) if cost>0 else 0.0
    markup={"inline_keyboard":[[
        {"text":"✅ CONTINUE","callback_data":f"v85:ACK_CONTINUE:{p['trade_id']}"},
        {"text":"💰 TAKE PROFIT","callback_data":f"v85:CLOSE_NOW:{p['trade_id']}"}
    ]]}
    telegram(
        f"{prefix} | {target_name} ACHIEVED 🎯\n\n"
        f"{sym}\nTarget: {float(target_price):.8f}\n"
        f"Profit: {pnl:+.2f} USDT\nProfit: {pct:+.2f}%",
        reply_markup=markup,
    )

def _higher_tf_exit_confirmation(sym):
    """15m/30m must confirm a low-TF profit warning before a 100% discretionary exit."""
    try:
        rows=[]; total=0
        for tf in ('15m','30m'):
            d=kl(sym,tf,120); c=d.iloc[-2]; prev=d.iloc[-3]
            score=0; reasons=[]
            r=float(c.rsi); rp=float(prev.rsi)
            k=float(c.stoch_k) if pd.notna(c.stoch_k) else 50
            ds=float(c.stoch_d) if pd.notna(c.stoch_d) else 50
            pos,_,mid,_=_bb_position(c)
            _,bear,_,bear_names=_candle_reversal_bidirectional(d)
            if r>=70 and r<rp: score+=1; reasons.append('RSI rolling down')
            if k>=75 and k<ds: score+=1; reasons.append('StochRSI bearish cross')
            if bear>=12: score+=2; reasons.append('bearish candle '+','.join(bear_names[:2]))
            if float(c.c)<mid: score+=1; reasons.append('below Bollinger midline')
            if pos>=0.92 and r>=70: score+=1; reasons.append('upper-band exhaustion')
            total+=score; rows.append((tf,score,reasons))
        confirmed=(rows[0][1]>=2 and rows[1][1]>=2 and total>=5)
        return confirmed, {'score':total,'frames':rows}
    except Exception as ex:
        return False, {'error':str(ex)[:120]}

def _notify_exit_watch(prefix, sym, p, low_diag, high_diag):
    now=time.time(); last=float(p.get('last_exit_watch_notice',0) or 0)
    if now-last < float(CFG.get('exit_watch_cooldown_sec',900)):
        return
    p['last_exit_watch_notice']=now
    telegram(
        f"{prefix} | PROFIT PROTECTION WATCH ⚠️\n\n{sym}\n"
        f"Small-TF warning: {', '.join(low_diag.get('reasons',[])[:3])}\n"
        f"15m/30m confirmation: NOT YET\nPosition continues; no full exit."
    )


def kl(sym, tf, n=260):
    raw = mg("/api/v3/klines", {"symbol": sym, "interval": tf, "limit": n})
    d = pd.DataFrame(
        raw,
        columns=["ot","o","h","l","c","v","ct","qv","n","tb","tq","x"],
    )
    for c in ["o","h","l","c","v","qv"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["time"] = pd.to_datetime(d["ot"], unit="ms", utc=True)
    d["e9"] = ema(d.c, 9)
    d["e20"] = ema(d.c, 20)
    d["e50"] = ema(d.c, 50)
    d["e200"] = ema(d.c, 200)
    d["rsi"] = rsi(d.c)
    d["stoch_k"], d["stoch_d"] = stoch_rsi_series(d["rsi"], 14, 3, 3)
    d["atr"] = atr(d)
    d["macd"] = ema(d.c, 12) - ema(d.c, 26)
    d["macd_sig"] = ema(d["macd"], 9)
    d["bb_mid"] = d.c.rolling(20).mean()
    _sd = d.c.rolling(20).std()
    d["bb_up"] = d["bb_mid"] + 2 * _sd
    d["bb_lo"] = d["bb_mid"] - 2 * _sd
    d["tenkan"] = (d.h.rolling(9).max() + d.l.rolling(9).min()) / 2
    d["kijun"] = (d.h.rolling(26).max() + d.l.rolling(26).min()) / 2
    d["ichi_a"] = ((d["tenkan"] + d["kijun"]) / 2).shift(26)
    d["ichi_b"] = ((d.h.rolling(52).max() + d.l.rolling(52).min()) / 2).shift(26)
    d["vma20"] = d.v.rolling(20).mean()
    d["rvol"] = d.v / d["vma20"].replace(0, np.nan)
    # Rolling VWAP and StochRSI for precise 1m/3m/5m entry timing.
    typical=(d.h+d.l+d.c)/3.0
    pv=typical*d.v
    d["vwap"] = pv.rolling(50, min_periods=10).sum() / d.v.rolling(50, min_periods=10).sum().replace(0,np.nan)
    rmin=d["rsi"].rolling(14).min(); rmax=d["rsi"].rolling(14).max()
    d["stoch_rsi"] = (d["rsi"]-rmin)/(rmax-rmin).replace(0,np.nan)
    return d

def universe():
    """
    ALL-PAIRS MODE:
    Scan every Spot USDT symbol that is TRADING on the real-market data source
    and is also available on Binance Spot Testnet for executable test orders.
    No 24h quote-volume, daily-range, or spread filter is used for SYMBOL SELECTION.
    """
    main = {}
    for s in mg("/api/v3/exchangeInfo")["symbols"]:
        base = s.get("baseAsset", "")
        if (
            s.get("status") == "TRADING"
            and s.get("quoteAsset") == "USDT"
            and s.get("isSpotTradingAllowed", True)
        ):
            if base not in STABLE and not any(base.endswith(x) for x in LEV):
                main[s["symbol"]] = s

    test = {
        s["symbol"]: s
        for s in tg("/api/v3/exchangeInfo")["symbols"]
        if (
            s.get("status") == "TRADING"
            and s.get("quoteAsset") == "USDT"
            and s.get("isSpotTradingAllowed", True)
        )
    }

    common = set(main) & set(test)
    t24 = {x["symbol"]: x for x in mg("/api/v3/ticker/24hr")}
    out = []

    for sym in common:
        try:
            a = t24.get(sym, {})
            hi = float(a.get("highPrice") or 0)
            lo = float(a.get("lowPrice") or 0)
            last = float(a.get("lastPrice") or 0)
            rng = ((hi - lo) / last) if last > 0 else 0.0
            out.append((rng, sym))
        except Exception:
            out.append((0.0, sym))

    out.sort(reverse=True)
    print(f"[UNIVERSE] ALL-PAIRS MODE main_usdt={len(main)} testnet_usdt={len(test)} common_scanned={len(out)}")
    return out

def _bullish_candle(d):
    """Closed-candle early trigger patterns only."""
    if len(d) < 4:
        return "None", 0
    a = d.iloc[-3]
    b = d.iloc[-2]  # last CLOSED candle
    body = abs(b.c - b.o)
    rng = max(b.h - b.l, 1e-12)
    lower = min(b.o, b.c) - b.l
    upper = b.h - max(b.o, b.c)

    if b.c > b.o and a.c < a.o and b.o <= a.c and b.c >= a.o:
        return "Bullish Engulfing", 12
    if lower >= max(body * 1.8, rng * 0.35) and upper <= rng * 0.25 and b.c >= b.o:
        return "Hammer / Bullish Pin", 10
    if b.c > b.o and body / rng >= 0.68:
        return "Bullish Expansion", 7
    return "None", 0

def _swing_lows(series, window=2):
    arr = series.to_numpy()
    out = []
    for i in range(window, len(arr)-window):
        if arr[i] <= np.nanmin(arr[i-window:i+window+1]):
            out.append((i, float(arr[i])))
    return out

def _swing_highs(series, window=2):
    arr = series.to_numpy()
    out = []
    for i in range(window, len(arr)-window):
        if arr[i] >= np.nanmax(arr[i-window:i+window+1]):
            out.append((i, float(arr[i])))
    return out

def _classical_setup(d):
    """Early classical setup detection on 5m. Returns model, score, points, targets, invalidation."""
    x = d.tail(90).reset_index(drop=True)
    last = float(x.iloc[-2].c)
    atrv = float(x.iloc[-2].atr)
    lows = _swing_lows(x.l, 2)
    highs = _swing_highs(x.h, 2)

    # Double bottom before/at neckline break.
    if len(lows) >= 2:
        (i1,l1),(i2,l2) = lows[-2], lows[-1]
        if i2-i1 >= 5 and abs(l1-l2)/max((l1+l2)/2,1e-12) <= 0.018:
            neck = float(x.h.iloc[i1:i2+1].max())
            near_break = last >= neck - 0.35*atrv
            if near_break:
                h = max(neck - (l1+l2)/2, atrv)
                return {
                    "name":"Double Bottom",
                    "score":16,
                    "points":[{"idx":i1,"price":l1,"label":"L1"},{"idx":i2,"price":l2,"label":"L2"},
                              {"idx":int(x.h.iloc[i1:i2+1].idxmax()),"price":neck,"label":"Neck"}],
                    "targets":[neck+h, neck+1.5*h, neck+2*h],
                    "invalidation":min(l1,l2)-0.25*atrv,
                    "breakout":neck,
                }

    # Compression / ascending triangle proxy: flat resistance + rising lows.
    recent = x.tail(45).reset_index(drop=True)
    res = float(recent.h.iloc[:-2].quantile(.90))
    lo_a = float(recent.l.iloc[:20].min())
    lo_b = float(recent.l.iloc[-20:].min())
    range_old = (float(recent.h.iloc[:20].max())-lo_a)/max(last,1e-12)
    range_new = (float(recent.h.iloc[-20:].max())-lo_b)/max(last,1e-12)
    if lo_b > lo_a and range_new < range_old*0.78 and last >= res - 0.30*atrv:
        height=max(res-lo_b,atrv)
        return {
            "name":"Ascending Triangle / Compression",
            "score":14,
            "points":[],
            "targets":[res+height, res+1.5*height, res+2*height],
            "invalidation":lo_b-0.25*atrv,
            "breakout":res,
        }

    # Tight base near 20-bar high.
    hi20=float(x.h.iloc[-22:-2].max())
    lo20=float(x.l.iloc[-22:-2].min())
    if (hi20-lo20)/max(last,1e-12) <= 0.035 and last >= hi20-0.35*atrv:
        return {
            "name":"Base / Breakout",
            "score":11,
            "points":[],
            "targets":[hi20+atrv,hi20+1.8*atrv,hi20+2.7*atrv],
            "invalidation":lo20-0.20*atrv,
            "breakout":hi20,
        }

    return {"name":"No confirmed model","score":0,"points":[],"targets":[],"invalidation":None,"breakout":None}

def _harmonic_candidate(d):
    """
    Conservative Fibonacci-ratio candidate label.
    Used as confluence, never as a sole entry reason.
    """
    x=d.tail(120).reset_index(drop=True)
    piv=[]
    for i in range(3,len(x)-3):
        v=float(x.c.iloc[i])
        if v == float(x.c.iloc[i-3:i+4].min()) or v == float(x.c.iloc[i-3:i+4].max()):
            piv.append((i,v))
    if len(piv)<5:
        return "None",0
    p=piv[-5:]
    legs=[abs(p[i+1][1]-p[i][1]) for i in range(4)]
    if min(legs)<=1e-12:
        return "None",0
    abxa=legs[1]/legs[0]
    bcab=legs[2]/legs[1]
    cdbc=legs[3]/legs[2]
    # Deliberately modest score: ratios are supportive, not decisive.
    if .55<=abxa<=.70 and .35<=bcab<=.90 and 1.10<=cdbc<=1.85:
        return "Gartley-like completion",7
    if .35<=abxa<=.55 and .35<=bcab<=.90 and 1.40<=cdbc<=2.80:
        return "Bat-like completion",6
    return "None",0

def _harmonic_prz(d5):
    """Independent open-formula harmonic/PRZ approximation.
    Uses confirmed swing pivots and Fibonacci ratio families; does not copy any protected script.
    Returns the potential reversal zone, invalidation and structure-derived targets.
    """
    x=d5.tail(160).reset_index(drop=True)
    piv=[]
    w=2
    for i in range(w, len(x)-w):
        lo=float(x.l.iloc[i]); hi=float(x.h.iloc[i])
        if lo <= float(x.l.iloc[i-w:i+w+1].min()): piv.append((i,lo,'L'))
        if hi >= float(x.h.iloc[i-w:i+w+1].max()): piv.append((i,hi,'H'))
    piv.sort(key=lambda z:z[0])
    # collapse adjacent same-type pivots, keep the more extreme
    c=[]
    for q in piv:
        if c and c[-1][2]==q[2]:
            if (q[2]=='L' and q[1]<c[-1][1]) or (q[2]=='H' and q[1]>c[-1][1]): c[-1]=q
        else: c.append(q)
    if len(c)<5:
        return {"name":"None","confidence":0.0,"prz_low":None,"prz_high":None,"entry":None,"stop":None,"targets":[],"points":[]}
    pts=c[-5:]
    prices=[z[1] for z in pts]
    types=[z[2] for z in pts]
    # bullish XABCD must finish with D low
    if types != ['L','H','L','H','L']:
        return {"name":"None","confidence":0.0,"prz_low":None,"prz_high":None,"entry":None,"stop":None,"targets":[],"points":pts}
    X,A,B,C,D=prices
    XA=A-X; AB=A-B; BC=C-B; CD=C-D
    if min(XA,AB,BC,CD)<=0:
        return {"name":"None","confidence":0.0,"prz_low":None,"prz_high":None,"entry":None,"stop":None,"targets":[],"points":pts}
    ab_xa=AB/XA; bc_ab=BC/AB; cd_bc=CD/BC; ad_xa=(A-D)/XA
    families=[
        ("Gartley", (.55,.70),(.382,.886),(1.13,1.75),(.72,.84)),
        ("Bat", (.35,.55),(.382,.886),(1.55,2.75),(.82,.93)),
        ("Butterfly", (.72,.84),(.382,.886),(1.55,2.75),(1.20,1.34)),
        ("Crab", (.35,.70),(.382,.886),(2.20,3.80),(1.50,1.72)),
        ("Deep Crab", (.82,.93),(.382,.886),(2.00,3.80),(1.50,1.72)),
    ]
    best=None
    for name,r1,r2,r3,r4 in families:
        checks=[r1[0]<=ab_xa<=r1[1], r2[0]<=bc_ab<=r2[1], r3[0]<=cd_bc<=r3[1], r4[0]<=ad_xa<=r4[1]]
        conf=sum(checks)/4.0
        if best is None or conf>best[1]: best=(name,conf)
    name,conf=best
    atrv=float(x.iloc[-2].atr)
    # PRZ surrounds D and projected D from XA family; keep zone compact for intraday timing.
    dproj=D
    half=max(0.18*atrv, abs(C-D)*0.05)
    prz_low=dproj-half; prz_high=dproj+half
    stop=min(D,prz_low)-CFG["structural_stop_atr_buffer"]*atrv
    # Harmonic recovery targets are based on the CD retracement / prior structure, not fixed R multiples.
    t1=D + 0.382*(C-D)
    t2=D + 0.618*(C-D)
    t3=max(B, D + 0.886*(C-D))
    return {"name":name,"confidence":conf,"prz_low":prz_low,"prz_high":prz_high,"entry":dproj,
            "stop":stop,"targets":[t1,t2,t3],"points":pts,
            "ratios":{"AB_XA":ab_xa,"BC_AB":bc_ab,"CD_BC":cd_bc,"AD_XA":ad_xa}}


def _entry_trigger(d1m,d3,d5,prz,model):
    """Fast 1m/3m/5m trigger. PRZ defines WHERE; momentum/volume/structure define WHEN."""
    c1=d1m.iloc[-2]; p1=d1m.iloc[-3]; c3=d3.iloc[-2]; c5=d5.iloc[-2]
    atr5=max(float(c5.atr),1e-12); last=float(c1.c)
    score=0; reasons=[]
    # Location: strongest requirement.
    low=prz.get("prz_low"); high=prz.get("prz_high")
    in_prz=False; chase=False; dist_prz_atr=999.0
    if low is not None and high is not None:
        if low <= last <= high:
            in_prz=True; dist_prz_atr=0.0; score+=30; reasons.append("Price inside harmonic PRZ +30")
        elif last>high:
            dist_prz_atr=(last-high)/atr5
            if dist_prz_atr <= CFG["retest_tolerance_atr"]:
                score+=20; reasons.append(f"Controlled PRZ retest/escape {dist_prz_atr:.2f} ATR +20")
            elif dist_prz_atr > CFG["max_prz_chase_atr"]:
                chase=True; reasons.append(f"PRZ already crossed by {dist_prz_atr:.2f} ATR - BLOCK")
        else:
            dist_prz_atr=(low-last)/atr5
            reasons.append(f"Still below PRZ by {dist_prz_atr:.2f} ATR - WAIT")
    # 1m reversal impulse / reclaim
    if float(c1.c)>float(c1.o) and float(c1.c)>float(p1.h):
        score+=18; reasons.append("1m bullish reclaim/impulse +18")
    elif float(c1.c)>float(c1.o):
        score+=9; reasons.append("1m bullish close +9")
    # VWAP/EMA reclaim; don't demand both.
    if pd.notna(c1.vwap) and float(c1.c)>=float(c1.vwap): score+=10; reasons.append("1m VWAP reclaimed +10")
    if float(c3.c)>=float(c3.e20): score+=8; reasons.append("3m EMA20 reclaimed +8")
    # Momentum turn from lower StochRSI is early, not late.
    sr1=float(c1.stoch_rsi) if pd.notna(c1.stoch_rsi) else .5
    srp=float(p1.stoch_rsi) if pd.notna(p1.stoch_rsi) else sr1
    if sr1>srp and srp<=0.35: score+=10; reasons.append("1m StochRSI turning up from lower zone +10")
    if 42<=float(c3.rsi)<=68 and float(c3.rsi)>float(d3.rsi.iloc[-3]): score+=8; reasons.append("3m RSI rising in healthy zone +8")
    rv1=float(c1.rvol) if pd.notna(c1.rvol) else 0
    rv3=float(c3.rvol) if pd.notna(c3.rvol) else 0
    if rv1>=1.15: score+=8; reasons.append(f"1m RVOL {rv1:.2f}x +8")
    if rv3>=CFG["min_rvol_3m"]: score+=6; reasons.append(f"3m RVOL {rv3:.2f}x +6")
    # Hard chase guards.
    ext_vwap=(last-float(c1.vwap))/atr5 if pd.notna(c1.vwap) else 0.0
    if ext_vwap>0.75: chase=True; reasons.append(f"Extended above 1m VWAP {ext_vwap:.2f} ATR - BLOCK")
    # Weighted evidence: harmonic remains preferred, but one weak confirmation group no longer vetoes a strong setup.
    weighted_entry_ok = (
        atok
        and late_state["state"]!="HARD_LATE"
        and not confluence["hard_block"]
        and quality>=52
        and (pattern_ok or confluence["score"]>=58 or trigger["score"]>=58)
    )
    accepted = weighted_entry_ok or momentum_entry_ok or softlate_alt_ok

    if accepted and quality>=82:
        grade="A"
    elif accepted and quality>=52:
        grade="B"
    elif late_state["state"]=="HARD_LATE" or confluence["hard_block"]:
        grade="HARD_LATE"
    elif recheck_ok or confluence["score"]>=48:
        grade="MOMENTUM_RECHECK"
    elif pattern_ok and late_state["state"]!="HARD_LATE" and not trigger["chase"]:
        grade="WAIT_PRZ"
    elif late_state["state"]=="SOFT_LATE":
        grade="SOFT_LATE"
    else:
        grade="REJECT"

    targets=[float(x) for x in harmonic.get("targets",[]) if x and x>trigger["last"]]
    if len(targets)<3:
        targets=[float(x) for x in model.get("targets",[]) if x and x>trigger["last"]]

    reasons=[
        f"PRZ model: {harmonic.get('name')} confidence {hconf*100:.0f}%",
        f"Entry trigger: {trigger['score']}/100",
        f"15m/1h confirmation: {confirm}/100",
        f"Late state: {late_state['state']}",
        f"RSI/StochRSI + candles + Bollinger timing: {'READY' if rsi_timing['ready'] else 'WAIT'} | 1m={rsi_timing['rsi1']:.1f} 3m={rsi_timing['rsi3']:.1f} 5m={rsi_timing['rsi5']:.1f} 15m={rsi_timing['rsi15']:.1f}",
    ] + confluence["reasons"] + trigger["reasons"] + late_state["reasons"] + confirm_reasons

    entry_status = (
        "PRZ" if trigger["in_prz"]
        else "RETEST" if trigger["accepted"]
        else "MOMENTUM_RECHECK" if grade=="MOMENTUM_RECHECK"
        else "WAIT"
    )

    analysis={
        "score":quality,
        "accepted":accepted,
        "pattern_name":harmonic.get("name","None"),
        "harmonic":harmonic.get("name","None"),
        "harmonic_confidence":hconf,
        "prz_low":harmonic.get("prz_low"),
        "prz_high":harmonic.get("prz_high"),
        "pattern_targets":targets,
        "pattern_invalidation":harmonic.get("stop"),
        "signal_price_real":trigger["last"],
        "leading_score":round(hconf*100),
        "timing_score":trigger["score"],
        "confirmation_score":confirm,
        "late_entry":late_state["state"] in ("SOFT_LATE","HARD_LATE"),
        "late_state":late_state["state"],
        "momentum_recheck":grade=="MOMENTUM_RECHECK",
        "direct_softlate_entry":bool(momentum_entry_ok),
        "softlate_alt_entry":bool(softlate_alt_ok),
        "entry_status":entry_status,
        "rvol1":trigger["rv1"],
        "rvol3":trigger["rv3"],
        "rsi3":float(d3.iloc[-2].rsi),
        "rsi5":float(d5.iloc[-2].rsi),
        "rsi15":float(d15.iloc[-2].rsi),
        "classical_model":model.get("name"),
        "late_metrics":late_state,
        "rsi_timing":rsi_timing,
        "weighted_confluence":confluence,
    }

    return {
        "grade":grade,
        "score":quality/100.0,
        "quality_100":quality,
        "path":harmonic.get("name","None"),
        "atrp":atrp,
        "rsi15":float(d15.iloc[-2].rsi),
        "rsi5":float(d5.iloc[-2].rsi),
        "rsi3":float(d3.iloc[-2].rsi),
        "volume_ratio":float(d5.iloc[-2].rvol) if pd.notna(d5.iloc[-2].rvol) else 0.0,
        "reasons":reasons,
        "trend_1h":bool(d1h.iloc[-2].c>d1h.iloc[-2].e20),
        "trend_15m":bool(d15.iloc[-2].c>d15.iloc[-2].e20),
        "analysis":analysis,
    }

RADAR_ROTATION_CURSOR = 0

def _clip(x, lo, hi):
    return max(lo, min(hi, float(x)))

def radar_score(sym):
    """
    Lightweight micro-momentum ranking only.
    EVERY common USDT pair is scanned. No symbol is permanently excluded.
    Deep strategy logic remains unchanged and is applied after ranking.
    """
    d1 = kl(sym, "1m", 80)
    d3 = kl(sym, "3m", 80)
    if len(d1) < 30 or len(d3) < 30:
        raise RuntimeError("insufficient radar candles")

    c1 = d1.iloc[-2]   # last CLOSED 1m candle
    c3 = d3.iloc[-2]   # last CLOSED 3m candle

    rv1 = float(c1.rvol) if pd.notna(c1.rvol) else 0.0
    rv3 = float(c3.rvol) if pd.notna(c3.rvol) else 0.0

    # Price impulse: recent movement, not 24h turnover.
    ret1_3 = float(c1.c / d1.iloc[-5].c - 1.0)       # ~3 closed minutes
    ret1_8 = float(c1.c / d1.iloc[-10].c - 1.0)      # ~8 closed minutes
    ret3_3 = float(c3.c / d3.iloc[-5].c - 1.0)       # ~9 minutes

    # Acceleration compares the newest 3-minute impulse with the preceding one.
    prev1_3 = float(d1.iloc[-5].c / d1.iloc[-8].c - 1.0)
    accel = ret1_3 - prev1_3

    e9s1 = float(c1.e9 / d1.iloc[-5].e9 - 1.0) if float(d1.iloc[-5].e9) else 0.0
    e9s3 = float(c3.e9 / d3.iloc[-5].e9 - 1.0) if float(d3.iloc[-5].e9) else 0.0

    prior_high_1 = float(d1.iloc[-22:-2].h.max())
    prior_high_3 = float(d3.iloc[-22:-2].h.max())
    near_break_1 = float(c1.c / max(prior_high_1, 1e-12) - 1.0)
    near_break_3 = float(c3.c / max(prior_high_3, 1e-12) - 1.0)

    rsi1 = float(c1.rsi) if pd.notna(c1.rsi) else 50.0
    rsi3 = float(c3.rsi) if pd.notna(c3.rsi) else 50.0

    # 0-100 score. RVOL is relative to the coin's own recent activity,
    # so small-cap and large-cap coins compete on current momentum, not 24h volume.
    volume_component = (
        _clip((rv1 - 0.75) * 22.0, 0, 24) +
        _clip((rv3 - 0.75) * 18.0, 0, 20)
    )
    impulse_component = (
        _clip(ret1_3 * 100 * 8.0, -8, 18) +
        _clip(ret1_8 * 100 * 3.5, -6, 14) +
        _clip(ret3_3 * 100 * 3.0, -6, 14)
    )
    accel_component = _clip(accel * 100 * 12.0, -8, 12)
    slope_component = (
        _clip(e9s1 * 100 * 7.0, -4, 8) +
        _clip(e9s3 * 100 * 4.0, -4, 8)
    )
    breakout_component = (
        _clip((near_break_1 + 0.006) * 900.0, 0, 8) +
        _clip((near_break_3 + 0.010) * 500.0, 0, 6)
    )

    # Avoid ranking pure exhaustion at the very top, but do NOT reject the symbol.
    exhaustion_penalty = 0.0
    if rsi1 >= 84:
        exhaustion_penalty += min(10.0, (rsi1 - 84) * 1.2)
    if rsi3 >= 82:
        exhaustion_penalty += min(10.0, (rsi3 - 82) * 1.0)

    score = _clip(
        18.0 + volume_component + impulse_component + accel_component +
        slope_component + breakout_component - exhaustion_penalty,
        0, 100
    )

    return {
        "symbol": sym,
        "score": round(score, 2),
        "rv1": round(rv1, 2),
        "rv3": round(rv3, 2),
        "ret1_3_pct": round(ret1_3 * 100, 3),
        "ret1_8_pct": round(ret1_8 * 100, 3),
        "ret3_9_pct": round(ret3_3 * 100, 3),
        "accel_pct": round(accel * 100, 3),
        "rsi1": round(rsi1, 1),
        "rsi3": round(rsi3, 1),
    }

def build_fast_radar(universe_now):
    """
    Stage 1: scan ALL pairs on 1m/3m concurrently.
    Stage 2: deep-analyze top momentum names plus a rotating reserve,
    so quiet/harmonic candidates are still periodically inspected.
    """
    global RADAR_ROTATION_CURSOR

    symbols = [sym for _, sym in universe_now]
    radar = []
    errors = 0
    started = time.time()

    from concurrent.futures import ThreadPoolExecutor, as_completed
    workers = int(CFG.get("radar_workers", 16))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(radar_score, sym): sym for sym in symbols}
        for fut in as_completed(futs):
            sym = futs[fut]
            try:
                radar.append(fut.result())
            except Exception as exr:
                errors += 1
                if errors <= 8:
                    print("[RADAR WARN]", sym, str(exr)[:100])

    radar.sort(key=lambda x: x["score"], reverse=True)

    top_n = int(CFG.get("radar_top_n", 48))
    reserve_n = int(CFG.get("radar_rotation_n", 12))
    top_symbols = [x["symbol"] for x in radar[:top_n]]

    # Rotating reserve = no permanent exclusion by momentum rank.
    remaining = [x["symbol"] for x in radar[top_n:]]
    reserve = []
    if remaining and reserve_n > 0:
        start = RADAR_ROTATION_CURSOR % len(remaining)
        for i in range(min(reserve_n, len(remaining))):
            reserve.append(remaining[(start + i) % len(remaining)])
        RADAR_ROTATION_CURSOR = (start + reserve_n) % len(remaining)

    selected = []
    seen = set()
    for sym in top_symbols + reserve:
        if sym not in seen:
            seen.add(sym)
            selected.append(sym)

    elapsed = time.time() - started
    print(
        f"[RADAR] all_pairs={len(symbols)} scored={len(radar)} errors={errors} "
        f"selected_deep={len(selected)} elapsed={elapsed:.1f}s"
    )
    print("[RADAR] TOP10:", [
        (x["symbol"], x["score"], x["rv1"], x["rv3"],
         x["ret1_3_pct"], x["accel_pct"], x["rsi1"], x["rsi3"])
        for x in radar[:10]
    ])
    return selected, radar



# ---------------------------
# BEST-EFFORT NEWS CONTEXT
# ---------------------------
def news_context(sym, max_items=4):
    base = sym.replace("USDT", "")
    terms = {base.lower()}
    # Common mappings to reduce false positives.
    aliases = {
        "BTC": {"bitcoin"},
        "ETH": {"ethereum"},
        "SOL": {"solana"},
        "XRP": {"ripple", "xrp"},
        "DOGE": {"dogecoin"},
        "ADA": {"cardano"},
        "AVAX": {"avalanche"},
        "LINK": {"chainlink"},
        "BNB": {"binance coin", "bnb"},
        "SUI": {"sui"},
        "ZEC": {"zcash"},
        "UNI": {"uniswap"},
        "ENA": {"ethena"},
        "PENGU": {"pudgy penguins", "pengu"},
    }
    terms |= aliases.get(base, set())

    hits = []
    for feed in NEWS_FEEDS:
        try:
            r = requests.get(feed, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
            if not r.ok:
                continue
            root = ET.fromstring(r.content)
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                low = title.lower()
                if any(re.search(rf"\b{re.escape(t)}\b", low) for t in terms):
                    hits.append({"title": title[:160], "link": link, "published": pub})
        except Exception:
            continue

    unique = []
    seen = set()
    for h in hits:
        if h["title"] in seen:
            continue
        seen.add(h["title"])
        unique.append(h)
        if len(unique) >= max_items:
            break
    return unique

def news_summary(sym):
    items = news_context(sym)
    if not items:
        return "News context: no directly-matched recent headline found in configured public feeds."
    lines = ["Recent public-news context (supporting only):"]
    for i, h in enumerate(items, 1):
        lines.append(f"{i}. {h['title']}")
    return "\n".join(lines)

# ---------------------------
# CHART
# ---------------------------
def make_chart(sym, entry, stop, tp1, tp2, tp3, analysis=None, title_suffix="Trade Plan"):
    Path(CFG["chart_dir"]).mkdir(exist_ok=True)
    d = kl(sym, "3m", 220).tail(160).copy()
    fig, ax = plt.subplots(figsize=(13, 7))
    x = mdates.date2num(d["time"].dt.to_pydatetime())
    width = 0.00135

    for xi, o, h, l, c in zip(x, d.o, d.h, d.l, d.c):
        ax.plot([xi, xi], [l, h], linewidth=.8)
        bottom=min(o,c)
        height=max(abs(c-o),max(abs(c)*0.00015,1e-12))
        ax.add_patch(plt.Rectangle((xi-width/2,bottom),width,height,fill=False,linewidth=.8))

    ax.plot(d["time"], d["e9"], label="EMA9", linewidth=1)
    ax.plot(d["time"], d["e20"], label="EMA20", linewidth=1)
    ax.plot(d["time"], d["e50"], label="EMA50", linewidth=1)
    ax.plot(d["time"], d["bb_up"], label="BB Upper", linewidth=.7)
    ax.plot(d["time"], d["bb_mid"], label="BB Mid", linewidth=.7)
    ax.plot(d["time"], d["bb_lo"], label="BB Lower", linewidth=.7)

    # Real-market model overlay. Execution levels remain listed separately in Telegram.
    if analysis:
        a=analysis
        model=a.get("pattern")
        if model:
            pts=model.get("points",[])
            # Points were detected on the most recent 60 bars; map approximately onto chart tail.
            base_idx=max(0,len(d)-60)
            px=[]; py=[]
            for p in pts:
                idx=min(len(d)-1,base_idx+int(p["idx"]))
                px.append(d["time"].iloc[idx]); py.append(float(p["price"]))
                ax.text(d["time"].iloc[idx],float(p["price"]),f" {p['label']}",fontsize=9)
            if len(px)>=2:
                ax.plot(px,py,marker="o",linewidth=1.3,label=model.get("name","Model"))
            for j,t in enumerate(model.get("targets",[])[:3],1):
                ax.axhline(float(t),linestyle=":",linewidth=1)
                ax.text(d["time"].iloc[-1],float(t),f" Model T{j} {float(t):.8f}",va="center",fontsize=8)
            inv=model.get("invalidation")
            if inv:
                ax.axhline(float(inv),linestyle=":",linewidth=1)
                ax.text(d["time"].iloc[-1],float(inv),f" Model invalidation {float(inv):.8f}",va="center",fontsize=8)

        signal=a.get("signal_price_real")
        if signal:
            ax.axhline(float(signal),linestyle="--",linewidth=1.2)
            ax.text(d["time"].iloc[-1],float(signal),f" REAL SIGNAL {float(signal):.8f}",va="center",fontsize=8)

    ax.set_title(f"{sym} — V8.5 PRZ CLEAN {title_suffix} (Real market 3m)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.tick_params(axis="x",rotation=30)
    ax.legend(loc="upper left")
    ax.grid(True,alpha=.2)
    fig.tight_layout()
    path=Path(CFG["chart_dir"])/f"{sym}_{int(time.time())}.png"
    fig.savefig(path,dpi=130)
    plt.close(fig)
    return str(path)

# ---------------------------
# STATE / COMPOUNDING
# ---------------------------
def csvrow(path, row):
    exists = Path(path).exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if not exists:
            w.writeheader()
        w.writerow(row)

def fresh():
    """Create a brand-new CLEAN state from the LIVE free USDT wallet balance."""
    usdt = bal("USDT")
    capital = usdt * CFG["allocation_pct"]
    return {
        "engine_id": ENGINE_ID,
        "created_at": iso(),
        "wallet_usdt_at_seed": usdt,
        "allocation_pct": CFG["allocation_pct"],
        "uae_day": uae_day(),
        "initial_capital": capital,
        "capital_base": capital,
        "day_start_capital": capital,
        "realized_day": 0.0,
        "realized_total": 0.0,
        "positions": {},
        "stopped": False,
        "reason": None,
        "last_daily_report": None,
        "telegram_update_offset": None,
        "closed_followups": [],
    }

def save(s):
    p = Path(CFG["state"])
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(s, indent=2), encoding="utf-8")
    tmp.replace(p)

def load():
    """Load only V8.5 PRZ CLEAN state; never fall back to any legacy V8.x state."""
    p = Path(CFG["state"])
    if not p.exists():
        s = fresh()
        save(s)
        return s

    try:
        s = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        bad = p.with_name(p.stem + f"_corrupt_{int(time.time())}" + p.suffix)
        try:
            p.replace(bad)
        except Exception:
            pass
        s = fresh()
        save(s)
        return s

    if s.get("engine_id") != ENGINE_ID:
        foreign = p.with_name(p.stem + f"_foreign_{int(time.time())}" + p.suffix)
        try:
            p.replace(foreign)
        except Exception:
            pass
        s = fresh()
        save(s)
        return s

    defaults = fresh()
    for k, v in defaults.items():
        if k not in s:
            s[k] = v
    return s

def day_ret(s):
    return s["realized_day"] / s["day_start_capital"] if s["day_start_capital"] else 0.0

def roll_day_if_needed(s):
    today = uae_day()
    if s.get("uae_day") == today:
        return

    old_day = s.get("uae_day")
    old_start = float(s.get("day_start_capital", 0))
    old_pnl = float(s.get("realized_day", 0))
    old_ret = old_pnl / old_start if old_start else 0

    csvrow(CFG["daily"], {
        "day": old_day,
        "start_capital": old_start,
        "realized_pnl": old_pnl,
        "return_pct": old_ret*100,
        "ending_capital_base": s.get("capital_base", 0),
    })

    # Compound ONLY realized PnL into allocated capital.
    new_capital = max(0.0, float(s["capital_base"]) + old_pnl)
    available = bal("USDT")
    new_capital = min(new_capital, available)

    s["capital_base"] = new_capital
    s["day_start_capital"] = new_capital
    s["realized_day"] = 0.0
    s["uae_day"] = today
    s["stopped"] = False
    s["reason"] = None
    s["last_daily_report"] = None
    save(s)

def risk_cash(s, grade):
    pct = CFG["risk_A"] if grade == "A" else CFG["risk_B"]
    # Profit lock: reduce risk after +1% and +2%.
    r = day_ret(s)
    if r >= 0.02:
        pct *= 0.35
    elif r >= 0.01:
        pct *= 0.60
    return s["capital_base"] * pct

# ---------------------------
# TP / POSITION MANAGEMENT
# ---------------------------
def adaptive_trailing_pct(sym):
    """Adaptive 0.40%-0.60% trail from real-market 5m ATR."""
    try:
        d = kl(sym, "5m", 80)
        c = d.iloc[-2]
        atrp = float(c.atr / c.c) if c.c else CFG["trailing_max_pct"]
        return min(CFG["trailing_max_pct"], max(CFG["trailing_min_pct"], atrp * CFG["trailing_atr_factor"]))
    except Exception:
        return CFG["trailing_max_pct"]

def split_qty(sym, qty):
    lot = fget(sym, "LOT_SIZE")
    step = float(lot.get("stepSize", "0.00000001"))
    q1 = floor_step(qty * CFG["tp1_pct"], step)
    q2 = floor_step(qty * CFG["tp2_pct"], step)
    q3 = floor_step(qty - q1 - q2, step)
    return q1, q2, q3

def create_targets(entry, dist, analysis=None):
    analysis=analysis or {}
    minp=float(CFG.get("intraday_min_structural_stop_pct",0.012))
    maxp=float(CFG.get("intraday_max_structural_stop_pct",0.055))
    stop_model=analysis.get("pattern_invalidation")
    model_pct=((entry-float(stop_model))/entry) if stop_model and 0<float(stop_model)<entry else 0.0
    stop_pct=max(minp,min(maxp,max(float(dist),model_pct)))
    stop=entry*(1-stop_pct)
    raw=[float(x) for x in analysis.get("pattern_targets",[]) if x and float(x)>entry]
    fallback=[entry*(1+CFG["tp1_r"]*stop_pct),entry*(1+CFG["tp2_r"]*stop_pct),entry*(1+CFG["tp3_r"]*stop_pct)]
    vals=sorted((raw+fallback)[:3])
    return stop,vals[0],vals[1],vals[2]

def position_open_risk_cash(p):
    entry = float(p.get("entry", 0))
    stop = float(p.get("stop_current", p.get("stop_initial", 0)))
    remaining_qty = sum(float(t.get("qty", 0)) for t in p.get("tranches", []) if t.get("status") == "OPEN")
    return max(0.0, entry - stop) * remaining_qty

def portfolio_open_risk_cash(s):
    return sum(position_open_risk_cash(p) for p in s.get("positions", {}).values())

def portfolio_risk_capacity_cash(s):
    return max(0.0, float(s["capital_base"]) * CFG["max_portfolio_open_risk_pct"] - portfolio_open_risk_cash(s))

def openpos(s, sym, e):
    desired_risk = risk_cash(s, e["grade"])
    risk = min(desired_risk, portfolio_risk_capacity_cash(s))
    raw_dist = CFG["atr_mult"] * e["atrp"]
    analysis=e.get("analysis",{})
    sig=float(analysis.get("signal_price_real") or 0)
    inv=analysis.get("pattern_invalidation")
    model_pct=((sig-float(inv))/sig) if sig>0 and inv and 0<float(inv)<sig else 0.0
    dist=max(float(CFG.get("intraday_min_structural_stop_pct",0.012)), min(float(CFG.get("intraday_max_structural_stop_pct",0.055)), max(raw_dist,model_pct)))
    if risk <= 0 or dist <= 0:
        return False

    # Risk cash remains fixed; a wider structural stop automatically reduces position size.
    quote = min(s["capital_base"] * CFG["max_single_position_allocation_pct"], risk / dist)
    if quote < 10.0:
        return False

    if symbol_locked_by_account(sym):
        return False

    r = buy(sym, quote)
    qty = float(r.get("executedQty", 0))
    spent = float(r.get("cummulativeQuoteQty", 0))
    if qty <= 0:
        return False

    entry = spent / qty
    stop, tp1, tp2, tp3 = create_targets(entry, dist, e.get("analysis",{}))
    q1, q2, q3 = split_qty(sym, qty)
    q23 = q2 + q3

    tranches = []
    try:
        if q1 > 0:
            oco1 = place_oco(sym, q1, tp1, stop)
            tranches.append({
                "name": "TP1", "qty": q1, "target": tp1,
                "oco": oco1["orderListId"], "status": "OPEN",
                "received": 0.0, "filled_qty": 0.0
            })

        if q23 > 0:
            oco23 = place_oco(sym, q23, tp3, stop)
            tranches.append({
                "name": "TP23_COMBINED", "qty": q23,
                "q2_planned": q2, "q3_planned": q3,
                "target": tp3, "oco": oco23["orderListId"],
                "status": "OPEN", "received": 0.0, "filled_qty": 0.0
            })
    except Exception as ex:
        print("[V8.5 PRZ CLEAN PROTECTION ERROR]", sym, ex)
        telegram(
            f"V8.5 PRZ CLEAN TESTNET | PROTECTION ERROR\n\n"
            f"{sym}\nInitial OCO protection failed. Emergency exit requested.\n"
            f"{str(ex)[:180]}"
        )
        for t in tranches:
            try:
                cancel_oco(sym, t["oco"])
            except Exception:
                pass
        try:
            market_sell(sym, qty)
        except Exception:
            pass
        return False

    trade_id = f"{sym}-{int(time.time())}"
    s["positions"][sym] = {
        "trade_id": trade_id,
        "origin_version": "V8.5 PRZ CLEAN",
        "qty": qty,
        "spent": spent,
        "entry": entry,
        "grade": e["grade"],
        "quality_100": e["quality_100"],
        "path": e["path"],
        "reasons": e["reasons"],
        "analysis_snapshot": e.get("analysis", {}),
        "signal_price_real": e.get("analysis", {}).get("signal_price_real"),
        "mfe_real_pct": 0.0,
        "mae_real_pct": 0.0,
        "stop_initial": stop,
        "stop_current": stop,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "tranches": tranches,
        "tp1_event_handled": False,
        "tp1_decision_deadline": None,
        "tp1_decision": None,
        "runner_active": False,
        "runner_high": 0.0,
        "runner_trail_pct": None,
        "opened_at": iso(),
    }
    save(s)

    news = news_summary(sym)
    msg = (
        f"V8.5 PRZ CLEAN TESTNET | OPEN TRADE ✅\n\n"
        f"Symbol: {sym}\n"
        f"Grade: {e['grade']} | Total Quality: {e['quality_100']}/100\n"
        f"Model: {e['path']}\n"
        f"Leading setup: {e.get('analysis',{}).get('leading_score',0)}/100\n"
        f"3m/5m entry timing: {e.get('analysis',{}).get('timing_score',0)}/100\n"
        f"15m/1h confirmation: {e.get('analysis',{}).get('confirmation_score',0)}/100\n"
        f"Entry status: {'LATE - BLOCKED' if e.get('analysis',{}).get('late_entry') else 'EARLY/OPTIMAL'}\n"
        f"RSI 3m/5m/15m: {e.get('rsi3',0):.1f} / {e.get('rsi5',0):.1f} / {e.get('rsi15',0):.1f}\n"
        f"RVOL 3m/5m: {e.get('analysis',{}).get('rvol3',0):.2f}x / {e.get('volume_ratio',0):.2f}x\n"
        f"Harmonic context: {e.get('analysis',{}).get('harmonic','None')}\n"
        f"Real-market signal price: {e.get('analysis',{}).get('signal_price_real',0):.8f}\n"
        f"Testnet execution entry: {entry:.8f}\n"
        f"SL: {stop:.8f}\n"
        f"TP1: {tp1:.8f} ({CFG['tp1_pct']*100:.0f}% qty)\n"
        f"TP2: {tp2:.8f} ({CFG['tp2_pct']*100:.0f}% qty)\n"
        f"TP3: {tp3:.8f} ({CFG['tp3_pct']*100:.0f}% qty)\n"
        f"Position value: {spent:.2f} USDT\n"
        f"Pattern targets (real market): "
        + (", ".join(f"{x:.8f}" for x in e.get("analysis",{}).get("pattern_targets",[])[:3]) or "None")
        + "\n\n"
        f"Technical reasons:\n- " + "\n- ".join(e["reasons"][:10]) + "\n\n"
        f"{news}\n\n"
        f"Protection: initial OCO protection; after TP1 breakeven; after TP2 final {CFG['tp3_pct']*100:.0f}% becomes adaptive trailing runner."
    )
    open_markup = {
        "inline_keyboard": [[
            {"text": "💰 CLOSE NOW", "callback_data": f"v85:CLOSE_NOW:{trade_id}"},
            {"text": "📊 STATUS", "callback_data": f"v85:STATUS:{trade_id}"}
        ]]
    }
    telegram(msg, reply_markup=open_markup)

    try:
        chart = make_chart(sym, entry, stop, tp1, tp2, tp3, e.get("analysis"))
        telegram_photo(chart, caption=f"{sym} V8.5 PRZ CLEAN | 3m trigger / 5m setup / 15m-1h confirmation")
    except Exception as ex:
        print("[CHART WARN]", sym, ex)

    print(f"[V8.5 PRZ CLEAN OPEN] {sym} {e['grade']} quality={e['quality_100']} spent={spent:.2f}")
    return True

def tranche_status(sym, tranche):
    try:
        received, filled_qty, status = oco_filled_quote(sym, tranche["oco"])
        if status == "ALL_DONE" and filled_qty > 0:
            return "FILLED", received, filled_qty
        if status in ("ALL_DONE", "REJECT"):
            return "CLOSED", received, filled_qty
        return "OPEN", 0.0, 0.0
    except Exception as ex:
        print("[TRANCHE WARN]", sym, tranche.get("name"), ex)
        return "UNKNOWN", 0.0, 0.0

def rearm_remaining_after_tp1(s, sym):
    p = s["positions"][sym]
    structural = _structural_stop(sym, p)
    p["stop_current"] = max(float(p.get("stop_initial",0)), structural)

    combined = next(
        (t for t in p["tranches"]
         if t["name"] == "TP23_COMBINED" and t["status"] == "OPEN"),
        None
    )
    if not combined:
        save(s)
        return

    try:
        cancel_oco(sym, combined["oco"])
    except Exception as ex:
        print("[V8.5 PRZ CLEAN CANCEL COMBINED WARN]", sym, ex)

    combined["status"] = "REPLACED"

    for name, q, target in [
        ("TP2", float(combined.get("q2_planned", 0)), p["tp2"]),
        ("TP3", float(combined.get("q3_planned", 0)), p["tp3"]),
    ]:
        if q <= 0:
            continue
        oco = place_oco(sym, q, target, p["stop_current"])
        p["tranches"].append({
            "name": name, "qty": q, "target": target,
            "oco": oco["orderListId"], "status": "OPEN",
            "received": 0.0, "filled_qty": 0.0
        })

    save(s)
    telegram(
        f"V8.5 PRZ CLEAN TESTNET | TP1 RE-ARM ✅\n\n"
        f"{sym}\nRemaining position is protected by STRUCTURAL stop (swing/VWAP/EMA/ATR), not rigid breakeven.\n"
        f"TP2 and TP3 are independent OCO targets."
    )

def ask_tp1_decision(s, sym):
    p = s["positions"][sym]
    deadline = time.time() + CFG["tp1_decision_timeout_sec"]
    p["tp1_decision_deadline"] = deadline
    p["tp1_decision"] = None
    save(s)

    tech_score = p.get("quality_100", 0)
    news = news_summary(sym)
    default = CFG["tp1_default_action"]

    markup = {
        "inline_keyboard": [[
            {"text": "✅ Continue to TP2/TP3", "callback_data": f"v85:CONTINUE:{p['trade_id']}"},
            {"text": "💰 Close Remaining", "callback_data": f"v85:CLOSE:{p['trade_id']}"},
        ]]
    }

    telegram(
        f"V8.5 PRZ CLEAN TESTNET | TP1 ACHIEVED 🎯\n\n"
        f"Symbol: {sym}\n"
        f"TP1: {p['tp1']:.8f}\n"
        f"Remaining position is protected by STRUCTURAL stop; normal pullbacks below TP1 are allowed while structure remains valid.\n"
        f"Original quality score: {tech_score}/100\n\n"
        f"{news}\n\n"
        f"You have {CFG['tp1_decision_timeout_sec']} seconds to choose.\n"
        f"If no response: {default} automatically.",
        reply_markup=markup,
    )

def process_telegram_callbacks(s):
    updates = telegram_updates(s.get("telegram_update_offset"), timeout=0)
    for u in updates:
        s["telegram_update_offset"] = u["update_id"] + 1
        cq = u.get("callback_query")
        if not cq:
            continue

        data = cq.get("data", "")
        callback_id = cq.get("id")
        if not data.startswith("v85:"):
            continue

        parts = data.split(":", 2)
        if len(parts) != 3:
            continue
        action, trade_id = parts[1], parts[2]

        found_sym = None
        for sym, p in s["positions"].items():
            if p.get("trade_id") == trade_id:
                found_sym = sym
                break

        if not found_sym:
            answer_callback(callback_id, "Trade is no longer active.")
            continue

        p = s["positions"][found_sym]

        if action == "STATUS":
            try:
                last = float(tg("/api/v3/ticker/price", {"symbol": found_sym})["price"])
                remaining_qty = sum(float(t.get("qty", 0)) for t in p.get("tranches", []) if t.get("status") == "OPEN")
                unreal = (last - float(p["entry"])) * remaining_qty
                answer_callback(callback_id, "Status sent.")
                telegram(
                    f"V8.5 PRZ CLEAN TESTNET | STATUS 📊\n\n"
                    f"Symbol: {found_sym}\n"
                    f"Entry: {p['entry']:.8f}\n"
                    f"Last: {last:.8f}\n"
                    f"Approx. open PnL: {unreal:+.2f} USDT\n"
                    f"Current protective stop: {p['stop_current']:.8f}"
                )
            except Exception:
                answer_callback(callback_id, "Could not fetch status.")
            continue

        if action == "CLOSE_NOW":
            answer_callback(callback_id, "Closing remaining position.")
            telegram(f"V8.5 PRZ CLEAN TESTNET | Manual close requested for {found_sym}.")
            close_remaining(s, found_sym, "USER_CLOSE_NOW")
            continue

        if action == "ACK_CONTINUE":
            answer_callback(callback_id, "Continue confirmed.")
            telegram(f"V8.5.11 | Continue confirmed for {found_sym}.")
            continue

        if p.get("tp1_decision") is not None:
            answer_callback(callback_id, "Decision already recorded.")
            continue

        if action in ("CONTINUE", "CLOSE"):
            p["tp1_decision"] = action
            save(s)
            answer_callback(callback_id, f"V8 decision: {action}")
            telegram(f"V8.5 PRZ CLEAN TESTNET | Decision received for {found_sym}: {action}")

def close_remaining(s, sym, reason):
    p = s["positions"][sym]
    remaining_qty = 0.0

    for t in p["tranches"]:
        if t["status"] in ("OPEN", "RUNNER"):
            try:
                if t["status"] == "OPEN" and t.get("oco") is not None:
                    cancel_oco(sym, t["oco"])
            except Exception:
                pass
            remaining_qty += float(t["qty"])
            t["status"] = "CANCELLED"

    market_received = 0.0
    if remaining_qty > 0:
        r = market_sell(sym, remaining_qty)
        if r:
            market_received = float(r.get("cummulativeQuoteQty", 0))

    filled_received = sum(
        float(t.get("received", 0))
        for t in p["tranches"] if t["status"] == "FILLED"
    )
    filled_qty = sum(
        float(t.get("filled_qty", 0))
        for t in p["tranches"] if t["status"] == "FILLED"
    )

    total_received = filled_received + market_received
    total_closed_qty = filled_qty + remaining_qty
    cost_basis = p["spent"] * (total_closed_qty / p["qty"]) if p["qty"] else 0.0
    pnl = total_received - cost_basis

    s["realized_day"] += pnl
    s["realized_total"] += pnl

    csvrow(CFG["trades"], {
        "time": iso(), "symbol": sym, "event": reason,
        "received": total_received, "pnl": pnl
    })

    telegram(
        f"V8.5 PRZ CLEAN TESTNET | POSITION CLOSED\n\n"
        f"Symbol: {sym}\nReason: {reason}\n"
        f"Total trade PnL: {pnl:+.2f} USDT\n"
        f"Daily realized: {s['realized_day']:+.2f} USDT"
    )

    queue_followup(s, sym, p, reason)
    del s["positions"][sym]
    save(s)

def finalize_if_done(s, sym):
    p = s["positions"][sym]
    if any(t["status"] in ("OPEN", "RUNNER") for t in p["tranches"]):
        return

    received = sum(
        float(t.get("received", 0))
        for t in p["tranches"] if t["status"] == "FILLED"
    )
    filled_qty = sum(
        float(t.get("filled_qty", 0))
        for t in p["tranches"] if t["status"] == "FILLED"
    )
    if filled_qty <= 0:
        return

    cost_basis = p["spent"] * (filled_qty / p["qty"]) if p["qty"] else 0.0
    pnl = received - cost_basis
    s["realized_day"] += pnl
    s["realized_total"] += pnl

    csvrow(CFG["trades"], {
        "time": iso(), "symbol": sym, "event": "FULLY_CLOSED",
        "received": received, "filled_qty": filled_qty, "pnl": pnl
    })

    telegram(
        f"V8.5 PRZ CLEAN TESTNET | TRADE COMPLETE ✅\n\n"
        f"Symbol: {sym}\nTotal received: {received:.2f} USDT\n"
        f"Trade PnL: {pnl:+.2f} USDT\n"
        f"Daily realized: {s['realized_day']:+.2f} USDT"
    )

    queue_followup(s, sym, p, "FULLY_CLOSED")
    del s["positions"][sym]
    save(s)

def update_mfe_mae(s):
    # Tracks real-market movement from the original signal, independent of Testnet execution.
    for sym,p in s.get("positions",{}).items():
        sp=float(p.get("signal_price_real") or 0)
        if sp<=0:
            continue
        try:
            real=float(mg("/api/v3/ticker/price",{"symbol":sym})["price"])
            move=(real-sp)/sp
            p["mfe_real_pct"]=max(float(p.get("mfe_real_pct",0)),move)
            p["mae_real_pct"]=min(float(p.get("mae_real_pct",0)),move)
        except Exception:
            pass

def queue_followup(s, sym, p, exit_reason, exit_real_price=None):
    sp=float(p.get("signal_price_real") or 0)
    if exit_real_price is None:
        try:
            exit_real_price=float(mg("/api/v3/ticker/price",{"symbol":sym})["price"])
        except Exception:
            exit_real_price=0
    s.setdefault("closed_followups",[]).append({
        "symbol":sym,
        "closed_at":time.time(),
        "signal_price_real":sp,
        "exit_real_price":exit_real_price,
        "reason":exit_reason,
        "analysis_snapshot":p.get("analysis_snapshot",{}),
        "mfe_real_pct":p.get("mfe_real_pct",0),
        "mae_real_pct":p.get("mae_real_pct",0),
        "checks":{}
    })
    save(s)

def process_followups(s):
    now=time.time()
    keep=[]
    for f in s.get("closed_followups",[]):
        age=(now-f["closed_at"])/60
        for m in CFG["post_exit_minutes"]:
            key=str(m)
            if age>=m and key not in f["checks"]:
                try:
                    px=float(mg("/api/v3/ticker/price",{"symbol":f["symbol"]})["price"])
                    f["checks"][key]=px
                except Exception:
                    pass
        if all(str(m) in f["checks"] for m in CFG["post_exit_minutes"]):
            sp=float(f.get("signal_price_real") or 0)
            ex=float(f.get("exit_real_price") or 0)
            moves={k:((v-ex)/ex*100 if ex else 0) for k,v in f["checks"].items()}
            a=f.get("analysis_snapshot",{})
            pts=a.get("pattern_targets",[])
            final_px=f["checks"].get("60",0)
            hit=[i+1 for i,t in enumerate(pts[:3]) if final_px and final_px>=float(t)]
            telegram(
                f"V8.5 PRZ CLEAN | POST-TRADE AUDIT 🔬\\n\\n"
                f"{f['symbol']} | Exit: {f['reason']}\\n"
                f"MFE from signal: {f['mfe_real_pct']*100:+.2f}%\\n"
                f"MAE from signal: {f['mae_real_pct']*100:+.2f}%\\n"
                f"After exit 5m: {moves.get('5',0):+.2f}%\\n"
                f"15m: {moves.get('15',0):+.2f}% | 30m: {moves.get('30',0):+.2f}% | 60m: {moves.get('60',0):+.2f}%\\n"
                f"Model at entry: {a.get('pattern_name','None')}\\n"
                f"Model targets reached by 60m: {hit if hit else 'None'}"
            )
            csvrow(CFG["audit"],{
                "time":iso(),"symbol":f["symbol"],"exit_reason":f["reason"],
                "model":a.get("pattern_name","None"),
                "score":a.get("score",0),
                "mfe_pct":f["mfe_real_pct"]*100,"mae_pct":f["mae_real_pct"]*100,
                "after5_pct":moves.get("5",0),"after15_pct":moves.get("15",0),
                "after30_pct":moves.get("30",0),"after60_pct":moves.get("60",0),
                "model_targets_hit":",".join(map(str,hit))
            })
            try:
                chart=make_chart(f["symbol"],0,0,0,0,0,a,title_suffix="Post-trade 60m audit")
                telegram_photo(chart,caption=f"{f['symbol']} post-trade audit | model and theoretical targets")
            except Exception:
                pass
        else:
            keep.append(f)
    s["closed_followups"]=keep
    save(s)

def activate_runner_after_tp2(s, sym):
    """After TP2 fills, cancel TP3 fixed target and manage final tranche with adaptive trailing."""
    p = s["positions"].get(sym)
    if not p or p.get("runner_active"):
        return
    tp2 = next((t for t in p.get("tranches", []) if t.get("name") == "TP2"), None)
    runner = next((t for t in p.get("tranches", []) if t.get("name") == "TP3" and t.get("status") == "OPEN"), None)
    if not tp2 or tp2.get("status") != "FILLED" or not runner:
        return
    try:
        cancel_oco(sym, runner["oco"])
    except Exception as ex:
        print("[V8.5 PRZ CLEAN RUNNER CANCEL WARN]", sym, ex)
    runner["status"] = "RUNNER"
    trail = adaptive_trailing_pct(sym)
    last = float(tg("/api/v3/ticker/price", {"symbol": sym})["price"])
    p["runner_active"] = True
    p["runner_high"] = last
    p["runner_trail_pct"] = trail
    p["stop_current"] = max(float(p.get("stop_current", 0)), last * (1-trail))
    save(s)
    telegram(f"V8.5 PRZ CLEAN TESTNET | RUNNER ACTIVE 🚀\n\n{sym}\nFinal {CFG['tp3_pct']*100:.0f}% is no longer capped by TP3.\nAdaptive trail: {trail*100:.2f}%\nCurrent protected level: {p['stop_current']:.8f}")

def manage_runner(s, sym):
    p = s["positions"].get(sym)
    if not p or not p.get("runner_active"):
        return False
    runner = next((t for t in p.get("tranches", []) if t.get("status") == "RUNNER"), None)
    if not runner:
        return False
    last = float(tg("/api/v3/ticker/price", {"symbol": sym})["price"])
    p["runner_high"] = max(float(p.get("runner_high", last)), last)
    # Re-evaluate volatility but never loosen an already protected stop.
    trail = adaptive_trailing_pct(sym)
    p["runner_trail_pct"] = trail
    candidate = p["runner_high"] * (1-trail)
    p["stop_current"] = max(float(p.get("stop_current", 0)), candidate)
    if last >= float(p.get("tp3",1e99)) and not p.get("tp3_milestone_notified"):
        p["tp3_milestone_notified"] = True
        _target_alert("V8.5.11", sym, p, "TP3", p.get("tp3",last), current_price=last)
    save(s)
    if last <= p["stop_current"]:
        qty = float(runner.get("qty", 0))
        r = market_sell(sym, qty) if qty > 0 else None
        runner["received"] = float(r.get("cummulativeQuoteQty", 0)) if r else 0.0
        runner["filled_qty"] = float(r.get("executedQty", 0)) if r else 0.0
        runner["status"] = "FILLED"
        p["runner_active"] = False
        save(s)
        telegram(f"V8.5 PRZ CLEAN TESTNET | TRAILING EXIT ✅\n\n{sym}\nHigh: {p['runner_high']:.8f}\nTrail: {trail*100:.2f}%\nExit trigger: {p['stop_current']:.8f}\nExecution: {last:.8f}")
        return True
    return False

def manage_positions(s):
    process_telegram_callbacks(s)

    for sym in list(s["positions"]):
        p = s["positions"].get(sym)
        if not p:
            continue

        protect_exit, protect_diag, protect_last = _profit_protection_signal(sym, p)
        if protect_exit:
            confirmed, high_diag = _higher_tf_exit_confirmation(sym)
            print(f"[PROFIT EXIT WATCH] {sym} low={protect_diag.get('score')} htf={high_diag.get('score')} confirmed={confirmed} last={protect_last:.8f}")
            if confirmed:
                close_remaining(s, sym, "MULTITF_CONFIRMED_PROFIT_EXIT")
                continue
            _notify_exit_watch("V8.5.11", sym, p, protect_diag, high_diag)
            save(s)

        # Update tranche statuses
        tp1_hit_now = False
        for t in p["tranches"]:
            if t["status"] != "OPEN":
                continue
            status, received, filled_qty = tranche_status(sym, t)
            if status == "FILLED":
                t["status"] = "FILLED"
                t["received"] = received
                t["filled_qty"] = filled_qty
                if t["name"] == "TP1":
                    tp1_hit_now = True
                if t["name"] in ("TP1","TP2"):
                    _target_alert("V8.5.11", sym, p, t["name"], t.get("target",0), received, filled_qty)
                else:
                    telegram(f"V8.5.11 | {t['name']} FILLED 🎯\n\n{sym}")
            elif status == "CLOSED":
                t["status"] = "CLOSED"
                t["received"] = received
                t["filled_qty"] = filled_qty

        save(s)

        activate_runner_after_tp2(s, sym)
        p = s["positions"].get(sym)
        if p and p.get("runner_active"):
            manage_runner(s, sym)
            p = s["positions"].get(sym)
            if not p:
                continue

        if tp1_hit_now and not p.get("tp1_event_handled"):
            # Immediately protect remaining tranches, THEN ask the user.
            rearm_remaining_after_tp1(s, sym)
            s["positions"][sym]["tp1_event_handled"] = True
            save(s)
            ask_tp1_decision(s, sym)
            p = s["positions"][sym]

        # Act on TP1 decision or timeout
        if p.get("tp1_event_handled") and p.get("tp1_decision_deadline"):
            decision = p.get("tp1_decision")
            if decision == "CLOSE":
                close_remaining(s, sym, "USER_CLOSE_AFTER_TP1")
                continue
            elif decision == "CONTINUE":
                p["tp1_decision_deadline"] = None
                save(s)
            elif time.time() >= p["tp1_decision_deadline"]:
                default = CFG["tp1_default_action"]
                p["tp1_decision"] = default
                p["tp1_decision_deadline"] = None
                save(s)
                telegram(
                    f"V8.5 PRZ CLEAN TESTNET | TP1 timeout for {sym}\n"
                    f"No response received. Default action: {default}."
                )
                if default == "CLOSE":
                    close_remaining(s, sym, "TP1_TIMEOUT_CLOSE")
                    continue

        finalize_if_done(s, sym)

# ---------------------------
# REPORTING / LIMITS
# ---------------------------
def maybe_daily_report(s):
    now = uae_now()
    today = now.strftime("%Y-%m-%d")
    if now.hour == 23 and now.minute >= 55 and s.get("last_daily_report") != today:
        current = s["capital_base"] + s["realized_day"]
        initial = s["initial_capital"]
        monthly_multiple = current / initial if initial else 0

        telegram(
            f"V8.5 PRZ CLEAN TESTNET | DAILY REPORT 📊\n\n"
            f"Date UAE: {today}\n"
            f"Capital base: {s['capital_base']:.2f} USDT\n"
            f"Realized today: {s['realized_day']:+.2f} USDT\n"
            f"Daily return: {day_ret(s)*100:+.3f}%\n"
            f"Estimated capital after today's realized PnL: {current:.2f} USDT\n"
            f"Growth vs initial allocated capital: {monthly_multiple:.3f}x\n"
            f"Open positions: {len(s['positions'])}\n"
            f"Daily stop/cap: -1% / NO CAP\n"
            f"Monthly 2x–3x objective: informational only; risk is NOT increased to catch up."
        )
        s["last_daily_report"] = today
        save(s)

def enforce_daily_limits(s):
    r = day_ret(s)
    if r <= CFG["daily_loss_stop_pct"] and not s["stopped"]:
        s["stopped"] = True
        s["reason"] = "DAILY_LOSS_STOP"
        telegram(
            f"V8.5 PRZ CLEAN TESTNET | DAILY LOSS STOP ⛔\n"
            f"Daily return: {r*100:+.3f}%\nNo new positions will be opened."
        )
        save(s)

    if CFG.get("daily_profit_cap_pct") is not None and r >= CFG["daily_profit_cap_pct"] and not s["stopped"]:
        s["stopped"] = True
        s["reason"] = "DAILY_PROFIT_CAP"
        telegram(
            f"V8.5 PRZ CLEAN TESTNET | DAILY PROFIT CAP ✅\n"
            f"Daily return: {r*100:+.3f}%\nNo new positions will be opened."
        )
        save(s)

# ---------------------------
# MAIN
# ---------------------------
def main():
    s = load()

    wallet_now = bal("USDT")
    allocated_now = float(s["capital_base"])
    print("=== V8.5 PRZ CLEAN TESTNET — ISOLATED STATE / SMART OCO / CONFLUENCE ===")
    print(f"Wallet free USDT: {wallet_now:.8f}")
    print(f"Allocated capital ({CFG['allocation_pct']*100:.0f}%): {allocated_now:.8f}")
    print(f"State file: {CFG['state']} | Engine: {ENGINE_ID}")
    print("ALL-PAIRS FAST RADAR 1m/3m | HARMONIC PRZ PREFERRED | SOFT-LATE FINAL ENTRY 52/42/Q45 | HARD-LATE BLOCK | 0.90% aggregate open risk")
    print("PRZ entry engine | dynamic model targets | structural stop after TP1 | adaptive runner | -1% daily stop | NO daily profit cap")

    telegram(
        "V8.5 PRZ CLEAN TESTNET | BOT ONLINE ✅\n\n"
        f"Wallet free USDT: {wallet_now:.2f}\n"
        f"Allocated capital (40%): {allocated_now:.2f} USDT\n"
        f"Persistent isolated state: {CFG['state']}\n"
        "1m/3m trigger | 5m Harmonic PRZ | 15m/1h context\n"
        "PRZ + VWAP/EMA + RSI/StochRSI + RVOL timing\n"
        "Dynamic pattern TP1/TP2/TP3 + structural trailing management\n"
        "Daily limits: -1% / NO DAILY PROFIT CAP."
    )

    while True:
        try:
            roll_day_if_needed(s)
            update_mfe_mae(s)
            manage_positions(s)
            process_followups(s)
            maybe_daily_report(s)
            enforce_daily_limits(s)

            if s["stopped"]:
                print("STOPPED:", s["reason"])
                time.sleep(CFG["scan_sec"])
                continue

            if portfolio_risk_capacity_cash(s) > 0:
                qualified = []
                diag_all = []
                diag_scanned = 0
                diag_errors = 0
                universe_now = universe()

                # FAST STAGE: every pair gets a 1m/3m momentum score.
                deep_symbols, radar_rows = build_fast_radar(universe_now)

                # DEEP STAGE: strategy-specific analysis only on the most relevant
                # names plus rotating reserve. This does not change entry rules.
                from concurrent.futures import ThreadPoolExecutor, as_completed
                deep_results = {}
                with ThreadPoolExecutor(max_workers=int(CFG.get("deep_workers", 10))) as ex:
                    futs = {ex.submit(evalsig, sym): sym for sym in deep_symbols if sym not in s["positions"]}
                    for fut in as_completed(futs):
                        sym = futs[fut]
                        try:
                            deep_results[sym] = fut.result()
                        except Exception as exd:
                            diag_errors += 1
                            print("[SCAN WARN]", sym, str(exd)[:90])

                for sym in deep_symbols:
                    if sym in s["positions"] or sym not in deep_results:
                        continue
                    e = deep_results[sym]
                    diag_scanned += 1
                    diag_all.append((float(e.get("score",0)), sym, e))
                    csvrow(CFG["scanner"], {
                        "time": iso(),
                        "symbol": sym,
                        "grade": e["grade"],
                        "quality_100": e["quality_100"],
                        "path": e["path"],
                        "atr_pct": round(e["atrp"]*100, 3),
                        "rsi3": round(e.get("rsi3",0), 2),
                        "rsi5": round(e.get("rsi5",0), 2),
                        "rsi15": round(e["rsi15"], 2),
                        "rvol3": round(e.get("analysis",{}).get("rvol3",0), 2),
                        "rvol5": round(e["volume_ratio"], 2),
                        "leading_score": e.get("analysis",{}).get("leading_score",0),
                        "timing_score": e.get("analysis",{}).get("timing_score",0),
                        "confirmation_score": e.get("analysis",{}).get("confirmation_score",0),
                        "late_entry": e.get("analysis",{}).get("late_entry",False),
                    })
                    if e["grade"] in ("A", "B"):
                        qualified.append((e["score"], sym, e))

                qualified.sort(reverse=True)
                diag_all.sort(reverse=True, key=lambda x: x[0])
                diag_grades = {}
                for _, _, de in diag_all:
                    dg = str(de.get("grade","UNKNOWN"))
                    diag_grades[dg] = diag_grades.get(dg,0) + 1
                print(f"[DIAG] Universe={len(universe_now)} DeepScanned={diag_scanned} Errors={diag_errors} Grades={diag_grades} Qualified={len(qualified)}")
                print("[DIAG] TOP5:", [
                    (x[1], x[2].get("grade"), round(float(x[0]),1),
                     x[2].get("analysis",{}).get("leading_score",0),
                     x[2].get("analysis",{}).get("timing_score",0),
                     x[2].get("analysis",{}).get("confirmation_score",0),
                     x[2].get("analysis",{}).get("late_entry",False),
                     x[2].get("analysis",{}).get("pattern_name",""))
                    for x in diag_all[:5]
                ])
                print(
                    "Qualified:",
                    [(x[1], x[2]["grade"], x[2]["path"], x[2]["quality_100"])
                     for x in qualified[:10]]
                )

                for _, sym, e in qualified:
                    if portfolio_risk_capacity_cash(s) <= 0:
                        break
                    if sym not in s["positions"]:
                        openpos(s, sym, e)

            print(
                "Positions:", list(s["positions"]),
                "Capital:", round(s["capital_base"], 2),
                "DailyPnL:", round(s["realized_day"], 2),
                "Daily%:", round(day_ret(s)*100, 3),
            )

        except Exception as ex:
            print("[V8.5 PRZ CLEAN LOOP ERROR]", repr(ex))
            telegram(
                f"V8.5 PRZ CLEAN TESTNET | LOOP ERROR ⚠️\n\n"
                f"{type(ex).__name__}: {str(ex)[:300]}\n"
                f"Bot will retry after 60 seconds."
            )
            time.sleep(60)
            continue

        time.sleep(CFG["scan_sec"])

if __name__ == "__main__":
    main()
