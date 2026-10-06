#!/usr/bin/env python3
# ============================================================
# E | HIT & RUN — V11.5 TP3+ 1M SMART EXIT / FULL POSITION — 11 SEP 2026
# High activity / controlled risk / resilient market data / adaptive entry evidence / pure virtual execution
# User-approved policy:
# - Minimum position value: 300 USDT
# - Flexible notional: 300 / 500 / 700 / 1000 / 2000+ when quality + risk allow
# - No daily trade-count cap
# - No daily profit cap
# - No fixed simultaneous-position count cap
# - Mandatory structure/ATR stop on every trade
# - V12.0: governing harmonic structure/SL/targets are 15m; fast 1m/3m/5m execution logic is preserved
# - TP1/TP2/TP3/TP4 are milestones only: no automatic partial selling
# - The full position remains open while the bullish thesis is healthy
# - Automatic safety exit remains active for hard stop, protected trail, or confirmed bearish reversal
# - Capital recycles after every close; realized profits compound into virtual cash
# - Binance is market-data only. No live/testnet orders are sent.
# - Agentic telemetry to the existing Master / Learning stack.
# ============================================================

import os, time, json, math, threading, random, csv
from pathlib import Path
from datetime import datetime, timezone, timedelta
import requests
import pandas as pd
import numpy as np

# === EMBEDDED ADVANCED MARKET INTELLIGENCE — STANDALONE ===

"""
ADVANCED MARKET INTELLIGENCE LAYER — 2026-09-08
Original OHLCV-derived implementation for the user's A/B/C/D trading engines.

Purpose:
- Improve entry reading without copying proprietary/invite-only indicator code.
- Keep all indicator families active as weighted evidence rather than stacking hard vetoes.
- Components: Regime, Market Structure, Liquidity Sweep/Reclaim, Volume Profile,
  Multi-horizon Momentum, FVG quality, Order-Block proxy, VWAP/location.

Important:
- Volume Profile and order-flow-like features are OHLCV approximations, not exchange L2 order flow.
- No indicator guarantees profitable trades. Use in Testnet/virtual mode while validating.
"""
import math
import numpy as np
import pandas as pd

def _clip(x, lo=0.0, hi=100.0):
    try: return max(lo, min(hi, float(x)))
    except Exception: return lo

def _series(df, name):
    aliases = {
        "o": ("o","open"), "h": ("h","high"), "l": ("l","low"),
        "c": ("c","close"), "v": ("v","volume")
    }
    for k in aliases[name]:
        if k in df.columns:
            return pd.to_numeric(df[k], errors="coerce")
    raise KeyError(name)

def _closed(df, min_rows=40):
    if df is None or len(df) < min_rows:
        return None
    x = df.iloc[:-1].copy() if len(df) > min_rows else df.copy()
    if len(x) < min_rows:
        return None
    return x

def _ema(s, n):
    return s.ewm(span=n, adjust=False).mean()

def _atr(df, n=14):
    h,l,c = _series(df,"h"),_series(df,"l"),_series(df,"c")
    pc=c.shift(1)
    tr=pd.concat([(h-l).abs(),(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()

def _rsi(c,n=14):
    d=c.diff()
    up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean()
    dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    rs=up/dn.replace(0,np.nan)
    return 100-100/(1+rs)

def _pivots(df,left=3,right=3,lookback=90):
    x=_closed(df, max(25,left+right+10))
    if x is None: return []
    x=x.tail(lookback)
    h,l=_series(x,"h").values,_series(x,"l").values
    out=[]
    for i in range(left,len(x)-right):
        if h[i] >= np.max(h[i-left:i+right+1]):
            out.append((i,"H",float(h[i])))
        if l[i] <= np.min(l[i-left:i+right+1]):
            out.append((i,"L",float(l[i])))
    out.sort(key=lambda z:z[0])
    return out

def regime_score(df):
    x=_closed(df,60)
    if x is None: return {"score":50.0,"regime":"UNKNOWN","trend":0.0,"volatility":0.0}
    c=_series(x,"c"); a=_atr(x,14)
    e20,e50=_ema(c,20),_ema(c,50)
    px=float(c.iloc[-1]); av=float(a.iloc[-1] or 0)
    slope=(float(e20.iloc[-1])/max(float(e20.iloc[-6]),1e-12)-1.0)*100
    spread=(float(e20.iloc[-1])/max(float(e50.iloc[-1]),1e-12)-1.0)*100
    atrpct=100*av/max(px,1e-12)
    recent=a.dropna().tail(80)
    vol_pct=float((recent <= av).mean()) if len(recent) else .5
    trend_pts=_clip(50 + slope*14 + spread*10,0,100)
    if px>e20.iloc[-1]>e50.iloc[-1] and slope>0: reg="TREND_UP"
    elif px<e20.iloc[-1]<e50.iloc[-1] and slope<0: reg="TREND_DOWN"
    elif vol_pct<.35: reg="COMPRESSION"
    elif vol_pct>.80: reg="HIGH_VOL"
    else: reg="RANGE_MIXED"
    # Long-entry friendliness, not absolute market quality.
    score=trend_pts
    if reg=="COMPRESSION": score=max(score,58)
    if reg=="HIGH_VOL": score-=6
    return {"score":round(_clip(score),1),"regime":reg,"trend":round(trend_pts,1),"atr_pct":round(atrpct,3),"vol_percentile":round(vol_pct,2)}

def structure_score(df):
    x=_closed(df,50)
    if x is None: return {"score":50.0,"state":"UNKNOWN","bos":False,"choch":False}
    c=_series(x,"c"); px=float(c.iloc[-1])
    piv=_pivots(x,3,3,100)
    highs=[p for p in piv if p[1]=="H"]; lows=[p for p in piv if p[1]=="L"]
    score=50.0; state="MIXED"; bos=False; choch=False
    if len(highs)>=2 and len(lows)>=2:
        hh=highs[-1][2]>highs[-2][2]
        hl=lows[-1][2]>lows[-2][2]
        lh=highs[-1][2]<highs[-2][2]
        ll=lows[-1][2]<lows[-2][2]
        if hh and hl: score=82; state="HH_HL_UPTREND"
        elif lh and ll: score=20; state="LH_LL_DOWNTREND"
        elif hl: score=67; state="HIGHER_LOW"
        elif hh: score=64; state="HIGHER_HIGH"
        prior_h=highs[-1][2]
        bos=px>prior_h
        if bos: score=min(100,score+12); state+="|BOS_UP"
        # bullish change after bearish sequence
        if len(highs)>=3 and len(lows)>=3:
            prev_bear=highs[-2][2]<highs[-3][2] and lows[-2][2]<lows[-3][2]
            choch=prev_bear and px>highs[-2][2]
            if choch: score=min(100,score+15); state+="|CHOCH_UP"
    return {"score":round(_clip(score),1),"state":state,"bos":bos,"choch":choch,
            "last_high":highs[-1][2] if highs else None,"last_low":lows[-1][2] if lows else None}

def liquidity_score(df):
    x=_closed(df,45)
    if x is None: return {"score":50.0,"event":"NONE"}
    h,l,c,o=_series(x,"h"),_series(x,"l"),_series(x,"c"),_series(x,"o")
    a=_atr(x,14); av=max(float(a.iloc[-1]),1e-12)
    cur=x.iloc[-1]
    ch,cl,cc,co=float(h.iloc[-1]),float(l.iloc[-1]),float(c.iloc[-1]),float(o.iloc[-1])
    prior_h=float(h.iloc[-22:-1].max()); prior_l=float(l.iloc[-22:-1].min())
    # Bullish sell-side liquidity sweep: wick below prior low then reclaim.
    sweep_low=cl<prior_l and cc>prior_l
    # Breakout and hold above buy-side liquidity.
    hold_high=cc>prior_h and cl>prior_h-0.35*av
    rejection=(cc>co and (cc-cl) > 1.5*max(abs(cc-co),1e-12))
    score=50.0; event="NONE"
    if sweep_low:
        score=92.0; event="SELL_SIDE_SWEEP_RECLAIM"
    elif hold_high:
        score=84.0; event="BUY_SIDE_BREAK_HOLD"
    elif rejection and cl <= prior_l+0.35*av:
        score=75.0; event="LOW_REJECTION"
    else:
        dist_low=(cc-prior_l)/av
        dist_high=(prior_h-cc)/av
        if 0<=dist_low<=0.8: score=66; event="NEAR_SELL_SIDE_LIQUIDITY"
        elif 0<=dist_high<=0.8: score=62; event="NEAR_BREAKOUT_LIQUIDITY"
    return {"score":round(_clip(score),1),"event":event,"prior_high":prior_h,"prior_low":prior_l}

def volume_profile_score(df,bins=32,value_area=.70):
    x=_closed(df,55)
    if x is None: return {"score":50.0,"poc":None,"vah":None,"val":None,"location":"UNKNOWN"}
    x=x.tail(120)
    h,l,c,v=_series(x,"h"),_series(x,"l"),_series(x,"c"),_series(x,"v").fillna(0)
    tp=(h+l+c)/3.0
    lo,hi=float(l.min()),float(h.max())
    if hi<=lo: return {"score":50.0,"poc":float(c.iloc[-1]),"vah":hi,"val":lo,"location":"FLAT"}
    edges=np.linspace(lo,hi,bins+1)
    idx=np.clip(np.digitize(tp.values,edges)-1,0,bins-1)
    hist=np.zeros(bins,float)
    for i,vol in zip(idx,v.values):
        hist[int(i)]+=max(float(vol),0.0)
    centers=(edges[:-1]+edges[1:])/2
    poc_i=int(np.argmax(hist)); poc=float(centers[poc_i])
    total=float(hist.sum())
    order=np.argsort(hist)[::-1]
    selected=[]; cum=0.0
    for i in order:
        selected.append(int(i)); cum+=hist[i]
        if total<=0 or cum/total>=value_area: break
    val=float(edges[min(selected)]) if selected else lo
    vah=float(edges[max(selected)+1]) if selected else hi
    px=float(c.iloc[-1])
    if val<=px<=vah:
        loc="VALUE_AREA"; base=64
        if px>=poc: base=68
    elif px>vah:
        loc="ABOVE_VAH"; base=78
    else:
        loc="BELOW_VAL"; base=40
    # Reward reclaim of value area from below.
    prev=float(c.iloc[-2])
    if prev<val and px>=val: base=88; loc="VAL_RECLAIM"
    if prev<=vah and px>vah: base=max(base,85); loc="VAH_BREAK"
    return {"score":round(_clip(base),1),"poc":poc,"vah":vah,"val":val,"location":loc}

def momentum_score(df):
    x=_closed(df,70)
    if x is None: return {"score":50.0,"state":"UNKNOWN"}
    c=_series(x,"c")
    a=_atr(x,14)
    px=float(c.iloc[-1]); atr=max(float(a.iloc[-1]),1e-12)
    horizons=(3,6,12,24)
    vals=[]
    for n in horizons:
        if len(c)>n:
            vals.append((px/float(c.iloc[-1-n])-1.0)*px/atr)
    raw=np.mean(vals) if vals else 0.0
    e9,e21=_ema(c,9),_ema(c,21)
    slope=(float(e9.iloc[-1])/max(float(e9.iloc[-5]),1e-12)-1.0)*px/atr
    r=float(_rsi(c,14).iloc[-1])
    score=50+raw*7+slope*8
    if 48<=r<=72: score+=8
    elif r>=84: score-=14
    elif r<30: score-=5
    state="POSITIVE" if score>=60 else "NEGATIVE" if score<45 else "NEUTRAL"
    return {"score":round(_clip(score),1),"state":state,"rsi":round(r,1),"raw":round(float(raw),3)}

def fvg_score(df):
    x=_closed(df,40)
    if x is None: return {"score":50.0,"event":"NONE"}
    h,l,c,v=_series(x,"h"),_series(x,"l"),_series(x,"c"),_series(x,"v")
    avg_v=v.rolling(20).mean().replace(0,np.nan)
    rv=(v/avg_v).replace([np.inf,-np.inf],np.nan).fillna(0)
    best=50.0; event="NONE"
    for i in range(max(2,len(x)-18),len(x)):
        # Bullish 3-candle FVG: low[i] > high[i-2]
        if float(l.iloc[i])>float(h.iloc[i-2]):
            gap=float(l.iloc[i]-h.iloc[i-2])
            atr=max(float(_atr(x,14).iloc[i]),1e-12)
            q=min(100,58 + 18*min(gap/atr,1.0) + 10*min(float(rv.iloc[i]) if pd.notna(rv.iloc[i]) else 0,2)/2)
            if q>best: best=q; event="BULLISH_FVG"
    return {"score":round(_clip(best),1),"event":event}

def order_block_score(df):
    x=_closed(df,45)
    if x is None: return {"score":50.0,"event":"NONE"}
    o,h,l,c,v=_series(x,"o"),_series(x,"h"),_series(x,"l"),_series(x,"c"),_series(x,"v")
    a=_atr(x,14); avgv=v.rolling(20).mean()
    px=float(c.iloc[-1]); best=50.0; event="NONE"; zone=None
    for i in range(max(2,len(x)-25),len(x)-2):
        bearish=float(c.iloc[i])<float(o.iloc[i])
        impulse=(float(c.iloc[i+2])-float(c.iloc[i]))/max(float(a.iloc[i+2]),1e-12)
        relv=float(v.iloc[i+1]/max(float(avgv.iloc[i+1]),1e-12)) if pd.notna(avgv.iloc[i+1]) else 0
        if bearish and impulse>1.2 and relv>1.0:
            zlo=float(l.iloc[i]); zhi=float(o.iloc[i])
            dist=0 if zlo<=px<=zhi else min(abs(px-zlo),abs(px-zhi))/max(float(a.iloc[-1]),1e-12)
            q=82 if dist<=0.4 else 70 if dist<=1.0 else 58
            if q>best: best=q; event="BULLISH_ORDER_BLOCK"; zone=(zlo,zhi)
    return {"score":round(_clip(best),1),"event":event,"zone":zone}

def vwap_score(df):
    x=_closed(df,40)
    if x is None: return {"score":50.0,"vwap":None,"state":"UNKNOWN"}
    h,l,c,v=_series(x,"h"),_series(x,"l"),_series(x,"c"),_series(x,"v")
    tp=(h+l+c)/3.0
    vv=v.tail(40); t=tp.tail(40)
    vw=float((t*vv).sum()/max(float(vv.sum()),1e-12))
    px=float(c.iloc[-1]); atr=max(float(_atr(x,14).iloc[-1]),1e-12)
    ext=(px-vw)/atr
    score=72 if 0<=ext<=0.9 else 62 if -0.5<=ext<0 else 52 if .9<ext<=1.6 else 38
    return {"score":score,"vwap":vw,"extension_atr":round(ext,2),"state":"ABOVE" if px>=vw else "BELOW"}

def advanced_long_intelligence(frames, weights=None):
    """
    frames: dict like {"3m":df, "5m":df, "15m":df, "1h":df, "4h":df, "1d":df}
    Returns a non-brittle weighted long-entry intelligence score.
    """
    if not frames: return {"score":50.0,"components":{},"reasons":["no frames"]}
    # Select execution and context frames without requiring all of them.
    def _first(*vals):
        for z in vals:
            if z is not None:
                return z
        return next(iter(frames.values()))
    exec_df=_first(frames.get("5m"),frames.get("15m"),frames.get("4h"))
    micro_df=_first(frames.get("3m"),exec_df)
    context_df=_first(frames.get("1h"),frames.get("4h"),frames.get("1d"),exec_df)

    comps={
        "regime":regime_score(context_df),
        "structure":structure_score(context_df),
        "liquidity":liquidity_score(micro_df),
        "volume_profile":volume_profile_score(exec_df),
        "momentum":momentum_score(micro_df),
        "fvg":fvg_score(exec_df),
        "order_block":order_block_score(exec_df),
        "vwap":vwap_score(exec_df),
    }
    w=weights or {
        "regime":0.13,"structure":0.20,"liquidity":0.18,"volume_profile":0.14,
        "momentum":0.14,"fvg":0.07,"order_block":0.07,"vwap":0.07
    }
    score=sum(float(comps[k]["score"])*float(w.get(k,0)) for k in comps)
    denom=sum(float(w.get(k,0)) for k in comps) or 1.0
    score=_clip(score/denom)

    positive=sum(1 for z in comps.values() if float(z.get("score",50))>=68)
    strong=sum(1 for z in comps.values() if float(z.get("score",50))>=80)
    negative=sum(1 for z in comps.values() if float(z.get("score",50))<42)

    # Confluence bonus is capped; no single indicator can manufacture a trade.
    score=_clip(score + min(8,strong*2) + min(4,max(0,positive-3)) - min(10,negative*3))
    reasons=[
        f"Regime {comps['regime']['score']:.0f} {comps['regime'].get('regime')}",
        f"Structure {comps['structure']['score']:.0f} {comps['structure'].get('state')}",
        f"Liquidity {comps['liquidity']['score']:.0f} {comps['liquidity'].get('event')}",
        f"VolumeProfile {comps['volume_profile']['score']:.0f} {comps['volume_profile'].get('location')}",
        f"Momentum {comps['momentum']['score']:.0f} {comps['momentum'].get('state')}",
        f"FVG {comps['fvg']['score']:.0f} {comps['fvg'].get('event')}",
        f"OrderBlock {comps['order_block']['score']:.0f} {comps['order_block'].get('event')}",
        f"VWAP {comps['vwap']['score']:.0f} {comps['vwap'].get('state')}",
    ]
    return {"score":round(score,1),"components":comps,"reasons":reasons,
            "positive_count":positive,"strong_count":strong,"negative_count":negative}

# === END EMBEDDED AMI ===

UAE = timezone(timedelta(hours=4))
STRATEGY_CODE = "E"
STRATEGY_NAME = "HIT & RUN"

# V17.0 — Structural Anti-Chase experiment. New Structural entries are blocked
# only after price extends >1.25% above causal Wave-1 high and before a confirmed Wave-4 reset.
STRUCTURAL_NO_CHASE_PCT = float(os.getenv("E_STRUCTURAL_NO_CHASE_PCT", "1.25"))

# V17.1 — Pre-TP1 Entry Protection. Before 30% of the Entry→TP1 path,
# intended maximum loss is 3 USDT per new V17.1 trade. Once 30% is reached,
# Entry Protection is permanently armed and a live break below Entry exits in full.
PRETP1_ENTRY_PROTECTION_TRIGGER = float(
    os.getenv("E_PRETP1_ENTRY_PROTECTION_TRIGGER", "0.30")
)
PRETP1_MAX_LOSS_USDT = float(
    os.getenv("E_PRETP1_MAX_LOSS_USDT", "3.00")
)

ENGINE_ID = "E-HITRUN-V17.2-MASTER-TELEGRAM"
# COST-PARITY: accounting only; signal/SL/TP logic unchanged.
SPOT_FEE_RATE = float(os.getenv("E_SPOT_FEE_RATE", "0.00075"))
VIRTUAL_EXECUTION_SLIPPAGE_BPS = float(os.getenv("E_VIRTUAL_EXECUTION_SLIPPAGE_BPS", "2.0"))

def _e_cost(amount):
    amount=max(0.0,float(amount or 0.0))
    return amount*SPOT_FEE_RATE, amount*max(0.0,VIRTUAL_EXECUTION_SLIPPAGE_BPS)/10000.0

def _e_estimated_net(p, px):
    entry=float(p.get("entry",0) or 0); qty=float(p.get("qty",0) or 0); gross=(float(px)-entry)*qty
    ef=float(p.get("entry_fee_usdt",0) or 0); es=float(p.get("entry_slippage_usdt",0) or 0)
    xf,xs=_e_cost(float(px)*qty)
    return gross, ef+es+xf+xs, gross-ef-es-xf-xs

# V17.2 — Virtual resting-stop execution model.
# When an observed price crosses the active stop, simulate a stop-market fill at
# the stop level plus a small configurable adverse slippage allowance instead of
# charging the entire polling gap to the trade. Binance remains market-data only.
VIRTUAL_STOP_SLIPPAGE_BPS = float(os.getenv("E_VIRTUAL_STOP_SLIPPAGE_BPS", "2.0"))

MARKET_ENDPOINTS = [
    "https://data-api.binance.vision", "https://api.binance.com",
    "https://api1.binance.com", "https://api2.binance.com", "https://api3.binance.com"
]
SESSION = requests.Session()
SESSION.headers.update({"User-Agent":"E-HitRun-R10H/2026.09"})

TG_TOKEN = os.getenv("E_TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", ""))
TG_CHAT = os.getenv("E_TELEGRAM_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID", ""))
TG_CALLBACKS_ENABLED = os.getenv("E_TELEGRAM_CALLBACKS_ENABLED","true").lower() in ("1","true","yes","on")
TG_CALLBACK_PREFIX = "e141"
AGENTIC_HUB_URL = os.getenv("AGENTIC_HUB_URL", "").rstrip("/")
AGENTIC_HUB_KEY = os.getenv("AGENTIC_HUB_KEY", "")
AGENTIC_SNAPSHOT_SEC = float(os.getenv("AGENTIC_SNAPSHOT_SEC", "30"))

STATE_PATH = Path(os.getenv("E_STATE_PATH", "/data/E_V11_3_CLEAN_B_STYLE_PROFIT_50TRADE_state.json"))
NOMINAL_CAPITAL = float(os.getenv("E_NOMINAL_CAPITAL", "10000"))
MIN_NOTIONAL = 300.0
MIN_QUOTE_VOLUME = float(os.getenv("E_MIN_QUOTE_VOLUME", "3000000"))
SCAN_LIMIT = int(os.getenv("E_SCAN_LIMIT", "140"))
SCAN_SEC = float(os.getenv("E_SCAN_SEC", "45"))
MIN_SCORE = float(os.getenv("E_MIN_SCORE", "64"))
MIN_ENTRY_TIMING = float(os.getenv("E_MIN_ENTRY_TIMING", "68"))
# V4: a score can discover/arm a setup, but cannot trigger entry by itself.
V4_MIN_RVOL = float(os.getenv("E_V4_MIN_RVOL", "0.90"))
V4_MIN_RSI = float(os.getenv("E_V4_MIN_RSI", "44"))
V4_MAX_RSI = float(os.getenv("E_V4_MAX_RSI", "82"))
V4_BASE_RISK_USDT = float(os.getenv("E_V4_BASE_RISK_USDT", "10"))
V4_BASE_TARGET_USDT = float(os.getenv("E_V4_BASE_TARGET_USDT", "20"))
V4_MAX_TARGET_USDT = float(os.getenv("E_V4_MAX_TARGET_USDT", "50"))
MIN_RR = float(os.getenv("E_MIN_RR", "1.00"))
PREFERRED_RR = float(os.getenv("E_PREFERRED_RR", "1.25"))
MAX_RISK_PER_TRADE_PCT = float(os.getenv("E_MAX_RISK_PER_TRADE_PCT", "1.00"))
# No fixed aggregate open-risk cap in Hit & Run; each trade is protected by its own smart SL.
MAX_TOTAL_OPEN_RISK_PCT = 0.0
MAX_STOP_PCT = float(os.getenv("E_MAX_STOP_PCT", "3.50"))
COOLDOWN_MIN = float(os.getenv("E_SYMBOL_COOLDOWN_MIN", "20"))

# R9 — resilient market-data layer / adaptive entry policy.
HTTP_RETRIES = int(os.getenv("E_HTTP_RETRIES", "3"))
HTTP_BACKOFF_BASE = float(os.getenv("E_HTTP_BACKOFF_BASE", "0.45"))
ENDPOINT_COOLDOWN_SEC = float(os.getenv("E_ENDPOINT_COOLDOWN_SEC", "45"))
EXCHANGEINFO_CACHE_SEC = float(os.getenv("E_EXCHANGEINFO_CACHE_SEC", "21600"))
TICKER24_CACHE_SEC = float(os.getenv("E_TICKER24_CACHE_SEC", "20"))
PRICE_STALE_SEC = float(os.getenv("E_PRICE_STALE_SEC", "90"))
ERROR_TG_COOLDOWN_SEC = float(os.getenv("E_ERROR_TG_COOLDOWN_SEC", "900"))
MIN_ACTUAL_LIQUIDITY_RVOL = float(os.getenv("E_MIN_ACTUAL_LIQUIDITY_RVOL", "0.70"))
MIN_CONFIRM_SCORE = float(os.getenv("E_MIN_CONFIRM_SCORE", "62"))
DECISION_AUDIT_PATH = Path(os.getenv("E_DECISION_AUDIT_PATH", "/data/E_V11_3_CLEAN_B_STYLE_PROFIT_decisions.csv"))
GATE_AUDIT_PATH = Path(os.getenv("E_GATE_AUDIT_PATH", "/data/E_V11_3_CLEAN_B_STYLE_PROFIT_gate_audit.csv"))
VALIDATION_LIMIT = int(os.getenv("E_VALIDATION_TRADES", "50"))
VALIDATION_REPORT_PATH = Path(os.getenv("E_VALIDATION_REPORT_PATH", "/data/E_V11_3_CLEAN_B_STYLE_PROFIT_50TRADE_REPORT.json"))

# FIX1 — gates proven necessary by the real V4 log review.
# All clock windows are UAE time. Sessions do not replace actual liquidity checks.
DEAD_START, DEAD_END = 0, 4
RESTRICTED_START, RESTRICTED_END = 4, 9
ACTIVE_START, ACTIVE_END = 9, 11
CONDITIONAL_START, CONDITIONAL_END = 11, 17
PRIME_START, PRIME_END = 17, 24

SESSION_ACTIVE_MIN_RVOL = float(os.getenv("E_SESSION_ACTIVE_MIN_RVOL", "1.10"))
SESSION_CONDITIONAL_MIN_RVOL = float(os.getenv("E_SESSION_CONDITIONAL_MIN_RVOL", "1.20"))
SESSION_RESTRICTED_MIN_RVOL = float(os.getenv("E_SESSION_RESTRICTED_MIN_RVOL", "1.35"))
SESSION_PRIME_MIN_RVOL = float(os.getenv("E_SESSION_PRIME_MIN_RVOL", "1.05"))
EXCEPTIONAL_RVOL = float(os.getenv("E_EXCEPTIONAL_RVOL", "2.50"))
YELLOW_MIN_OPP = float(os.getenv("E_YELLOW_MIN_OPP", "75"))
YELLOW_MIN_TIMING = float(os.getenv("E_YELLOW_MIN_TIMING", "85"))

# V14.4 — StochRSI 1m is the fast execution/exit timing trigger; RSI remains context only.
STOCHRSI_RSI_LEN = int(os.getenv("E_STOCHRSI_RSI_LEN", "14"))
STOCHRSI_STOCH_LEN = int(os.getenv("E_STOCHRSI_STOCH_LEN", "14"))
STOCHRSI_K_SMOOTH = int(os.getenv("E_STOCHRSI_K_SMOOTH", "3"))
STOCHRSI_D_SMOOTH = int(os.getenv("E_STOCHRSI_D_SMOOTH", "3"))
STOCHRSI_RESET_MAX = float(os.getenv("E_STOCHRSI_RESET_MAX", "25"))
STOCHRSI_OVERBOUGHT = float(os.getenv("E_STOCHRSI_OVERBOUGHT", "80"))
STOCHRSI_EXIT_MIN_PROFIT_PCT = float(os.getenv("E_STOCHRSI_EXIT_MIN_PROFIT_PCT", "0.20"))

# === V11.8 EXCEPTIONAL OPPORTUNITY MODE (isolated entry enhancement) ===
# Purpose: in RED market conditions, allow only rare coins with strong independent relative strength.
# GREEN/YELLOW normal E-core behavior is unchanged.
EOM_ENABLED = os.getenv("E_EXCEPTIONAL_MODE","true").lower() in ("1","true","yes","on")
EOM_MIN_HARMONIC_CONF = float(os.getenv("E_EOM_MIN_HARMONIC_CONF","0.90"))
EOM_MIN_OPPORTUNITY = float(os.getenv("E_EOM_MIN_OPPORTUNITY","90"))
EOM_MIN_TIMING = float(os.getenv("E_EOM_MIN_TIMING","88"))
EOM_MIN_CONFIRM = float(os.getenv("E_EOM_MIN_CONFIRM","82"))
EOM_MIN_RVOL = float(os.getenv("E_EOM_MIN_RVOL","1.60"))
EOM_MIN_RS5 = float(os.getenv("E_EOM_MIN_RS5","0.35"))     # percentage-point edge vs BTC 5m
EOM_MIN_RS15 = float(os.getenv("E_EOM_MIN_RS15","0.45"))   # percentage-point edge vs BTC 15m
EOM_MAX_RED_NOTIONAL = float(os.getenv("E_EOM_MAX_RED_NOTIONAL","700"))
EOM_CRITICAL_BREADTH = float(os.getenv("E_EOM_CRITICAL_BREADTH","30"))
EOM_CRITICAL_BTC5 = float(os.getenv("E_EOM_CRITICAL_BTC5","-0.70"))
EOM_CRITICAL_BTC15 = float(os.getenv("E_EOM_CRITICAL_BTC15","-0.50"))

# Optional bridge for a future news/catalyst agent.
# A catalyst exception is NEVER enough by itself; exceptional liquidity + strong market confirmation are still mandatory.
CATALYST_FILE = Path(os.getenv("E_CONFIRMED_CATALYST_FILE", "/data/E_CONFIRMED_CATALYSTS.json"))

# Noise protection: structural invalidation is buffered, then size is reduced if the risk budget is exceeded.
MIN_STOP_PCT = float(os.getenv("E_MIN_STOP_PCT", "0.65"))

# V11.4 — targets are milestones; the whole remaining position is protected and managed.
RUNNER_TRAIL_ATR_MULT = float(os.getenv("E_RUNNER_TRAIL_ATR_MULT", "1.20"))
RUNNER_TRAIL_MIN_PCT = float(os.getenv("E_RUNNER_TRAIL_MIN_PCT", "0.35"))
RUNNER_TRAIL_MAX_PCT = float(os.getenv("E_RUNNER_TRAIL_MAX_PCT", "1.50"))
CONFIRMED_REVERSAL_EXIT = os.getenv("E_CONFIRMED_REVERSAL_EXIT", "1").strip().lower() not in ("0","false","no","off")
REVERSAL_MIN_PROFIT_PCT = float(os.getenv("E_REVERSAL_MIN_PROFIT_PCT", "0.20"))


def _session_name(dt=None):
    dt = dt or datetime.now(UAE)
    h = dt.hour + dt.minute/60.0
    if DEAD_START <= h < DEAD_END: return "DEAD_00_04"
    if RESTRICTED_START <= h < RESTRICTED_END: return "RESTRICTED_04_09"
    if ACTIVE_START <= h < ACTIVE_END: return "ACTIVE_09_11"
    if CONDITIONAL_START <= h < CONDITIONAL_END: return "CONDITIONAL_11_17"
    return "PRIME_17_24"

def _confirmed_catalyst(symbol):
    """Reads an optional catalyst feed written by the Agentic/news layer. Never fabricates news."""
    try:
        if not CATALYST_FILE.exists(): return False
        obj=json.loads(CATALYST_FILE.read_text())
        rows=obj if isinstance(obj,list) else obj.get("symbols",obj.get("catalysts",[]))
        now=time.time()
        for x in rows:
            if isinstance(x,str) and x.upper()==symbol.upper(): return True
            if isinstance(x,dict) and str(x.get("symbol","")).upper()==symbol.upper():
                exp=float(x.get("expires_at", now+1))
                confirmed=bool(x.get("confirmed",False))
                positive=bool(x.get("positive",False))
                if confirmed and positive and exp>=now: return True
    except Exception:
        pass
    return False

def session_liquidity_gate(setup):
    """V14.2: UAE session hard gate + market/liquidity confirmation.
    00:00-03:59 UAE: no NEW entries. Existing positions remain fully managed.
    04:00-08:59 UAE: Asian reopen permits new entries only in a positive (GREEN) regime.
    """
    sym=setup["symbol"]; session=_session_name()
    if session=="DEAD_00_04":
        return False,session,"HARD_SESSION_BLOCK_00_04_UAE_NO_NEW_ENTRY",False
    mode0=str((setup.get("regime") or {}).get("mode","YELLOW")).upper()
    # V15: market regime remains the default guard, but a truly independent coin may be evaluated separately.
    # RED exception is intentionally much stricter than YELLOW and requires HTF structural breakout + exceptional coin strength.
    ex0=setup.get("exceptional_coin",{}) or {}
    independent_exception=bool(ex0.get("eligible",False))
    if mode0=="RED" and not independent_exception:
        return False,session,"RED_REGIME_NO_NEW_LONG_UNLESS_EXCEPTIONAL_STRUCTURAL",False
    if mode0=="YELLOW":
        harm0=setup.get("harmonic_assist",{}) or {}
        opp0=float(setup.get("opportunity_score",0) or 0); timing0=float(setup.get("entry_timing_score",0) or 0)
        cs0=float((setup.get("structure_state") or {}).get("confirm_score",0) or 0)
        yellow_harmonic=bool(harm0.get("long_alignment",False) and
                              float(harm0.get("confidence",0) or 0)>=HARMONIC_STRONG_CONF and
                              opp0>=YELLOW_MIN_OPP and timing0>=YELLOW_MIN_TIMING and
                              cs0>=MIN_CONFIRM_SCORE and not setup.get("late_chase"))
        if not (yellow_harmonic or independent_exception):
            return False,session,"YELLOW_REQUIRES_EXCEPTIONAL_HARMONIC_OR_COIN",False
    opp=float(setup["opportunity_score"]); timing=float(setup["entry_timing_score"])
    harm=setup.get("harmonic_assist",{}) or {}
    harm_long=bool(harm.get("long_alignment",False)); harm_bear=bool(harm.get("bearish_conflict",False))
    borderline_gap=max(0.0, MIN_ENTRY_TIMING-timing)
    harmonic_borderline_override=bool(harm_long and float(harm.get("confidence",0))>=HARMONIC_STRONG_CONF and
                                      borderline_gap<=HARMONIC_BORDERLINE_TIMING_GAP and not setup.get("late_chase"))
    # Shadow mode records what Harmonic assistance WOULD change while preserving R9 decisions.
    if HARMONIC_SHADOW_ONLY and (harm_long or harm_bear or harmonic_borderline_override):
        emit("TRACK",sym,score=opp,reason=("R10H_SHADOW_BULLISH_ASSIST" if harm_long else "R10H_SHADOW_BEARISH_CONFLICT"),
             payload={**setup,"harmonic_borderline_override":harmonic_borderline_override,"timing_gap":borderline_gap})
    rv=float(setup.get("vol_ratio",0.0)); cs=float((setup.get("structure_state") or {}).get("confirm_score",0.0))
    regime=setup.get("regime",{}) or {}; mode=str(regime.get("mode","YELLOW")).upper()
    breadth=float(regime.get("breadth",50.0)); btc5=float(regime.get("btc5",0.0)); btc15=float(regime.get("btc15",0.0))
    catalyst=_confirmed_catalyst(sym)

    exceptional=(rv>=EXCEPTIONAL_RVOL and opp>=88 and timing>=84 and cs>=78 and breadth>=52 and btc15>-0.15)
    catalyst_exception=bool(catalyst and exceptional)

    if rv < MIN_ACTUAL_LIQUIDITY_RVOL:
        return False,session,"ACTUAL_LIQUIDITY_TOO_LOW",False

    # V15 separation: once a coin independently satisfies the strict ECM + HTF structural criteria,
    # do not re-veto it with broad-market opportunity/timing thresholds. 1m execution confirmation
    # is still mandatory later in try_open(), and 00:00-04:00 UAE remains an absolute block.
    if independent_exception:
        return True,session,"INDEPENDENT_EXCEPTIONAL_STRUCTURAL_PASS_TO_1M_TIMING",True

    # Severe RED is a hard long-entry veto unless the setup is exceptional.
    severe_red=(mode=="RED" and breadth<38 and btc5<-0.35 and btc15<-0.20)
    if severe_red and not exceptional:
        return False,session,"SEVERE_RED_REGIME_NO_LONG",False

    # Session adjusts the required evidence, but no UAE clock window alone blocks crypto trading.
    session_adj={"DEAD_00_04":6.0,"RESTRICTED_04_09":4.0,"ACTIVE_09_11":0.0,"CONDITIONAL_11_17":2.0,"PRIME_17_24":0.0}.get(session,2.0)
    regime_adj=5.0 if mode=="RED" else (1.5 if mode=="YELLOW" else 0.0)
    required_opp=MIN_SCORE+session_adj*0.35+regime_adj
    required_timing=MIN_ENTRY_TIMING+session_adj+regime_adj
    required_confirm=MIN_CONFIRM_SCORE+session_adj*0.7+regime_adj

    ok=(opp>=required_opp and timing>=required_timing and cs>=required_confirm)
    if ok:
        return True,session,f"ADAPTIVE_PASS opp>={required_opp:.1f} timing>={required_timing:.1f} confirm>={required_confirm:.1f}",False

    # V2: a near-threshold setup is not discarded when confirmation is materially stronger.
    # This is deliberately narrow: never RED, never late-chase, never bearish-harmonic conflict.
    opp_gap=max(0.0, required_opp-opp); timing_gap=max(0.0, required_timing-timing)
    borderline_pass=bool(mode!="RED" and not setup.get("late_chase") and not harm_bear and
                         rv>=V4_MIN_RVOL and opp_gap<=1.50 and timing_gap<=2.00 and
                         cs>=required_confirm+4.0)
    if borderline_pass:
        return True,session,f"ADAPTIVE_BORDERLINE_PASS opp_gap={opp_gap:.1f} timing_gap={timing_gap:.1f} confirm_edge={cs-required_confirm:.1f}",False
    if catalyst_exception:
        return True,session,"CONFIRMED_CATALYST_EXCEPTION",True
    return False,session,f"ADAPTIVE_WAIT opp={opp:.1f}/{required_opp:.1f} timing={timing:.1f}/{required_timing:.1f} confirm={cs:.1f}/{required_confirm:.1f}",False

def smart_target(setup, notional):
    """Target = quality target capped by reachable structure/VP/ATR room. Skip if room is too small."""
    p=float(setup["price"])
    q=min(float(setup["opportunity_score"]),float(setup["entry_timing_score"]))
    base=max(10.0, V4_BASE_TARGET_USDT*(float(notional)/500.0))
    if q>=90: base*=1.25
    elif q<78: base*=0.80
    base=min(V4_MAX_TARGET_USDT,base)

    candidates=[]
    vp=setup.get("volume_profile",{}) or {}
    st=setup.get("structure_state",{}) or {}
    for x in [vp.get("vah"), (st.get("m3") or {}).get("pivot_high"), (st.get("m15") or {}).get("pivot_high")]:
        try:
            x=float(x)
            if x>p*1.001: candidates.append(x)
        except Exception: pass

    structural_room=None
    if candidates:
        nearest=min(candidates)
        structural_room=max(0.0, (nearest/p-1.0)*float(notional)*0.85)

    atr_room=float(notional)*(float(setup.get("atr_pct",0.0))/100.0)*2.2
    room_candidates=[x for x in [structural_room, atr_room] if x is not None and x>0]
    reachable=min(room_candidates) if room_candidates else base
    target=min(base, reachable, V4_MAX_TARGET_USDT)

    # V4 SCALPER ECONOMY:
    # TARGET_ROOM is no longer a hard-veto based on an arbitrary percentage of the
    # preferred target. For Hit & Run, use the market-reachable target and let the
    # mandatory R:R gate decide whether the trade is economically valid.
    # We only reject if there is effectively no positive room at all.
    cs=float((setup.get("structure_state") or {}).get("confirm_score",0.0))
    timing=float(setup.get("entry_timing_score",0) or 0)
    opp=float(setup.get("opportunity_score",0) or 0)
    if target <= 0:
        return 0.0, {"base":round(base,2),"reachable":round(reachable,2),"structural_room":structural_room,
                     "atr_room":round(atr_room,2),"reason":"NO_POSITIVE_TARGET_ROOM",
                     "timing":round(timing,2),"opp":round(opp,2),"confirm":round(cs,2)}

    ratio = target/max(base,1e-9)
    if ratio >= 0.70:
        tier="FULL_STRUCTURE_ATR_TARGET"
    elif ratio >= 0.40:
        tier="SCALP_REDUCED_TARGET"
    else:
        tier="MICRO_QUICK_HIT_TARGET"
    return round(target,2), {"base":round(base,2),"reachable":round(reachable,2),"structural_room":structural_room,
                            "atr_room":round(atr_room,2),"reason":tier,"room_ratio":round(ratio,3),
                            "timing":round(timing,2),"opp":round(opp,2),"confirm":round(cs,2)}


_last_snapshot = 0.0


def now_uae(): return datetime.now(UAE).isoformat()

# R9 market-data health/cache state.
_ENDPOINT_HEALTH = {b:{"fails":0,"down_until":0.0} for b in MARKET_ENDPOINTS}
_HTTP_CACHE = {}
_LAST_PRICE = {}
_ERROR_NOTICE = {"last":0.0,"active":False,"count":0}

def _cache_get(key, ttl):
    row=_HTTP_CACHE.get(key)
    if not row: return None
    ts,val=row
    return val if time.time()-ts <= ttl else None

def _cache_put(key, val):
    _HTTP_CACHE[key]=(time.time(), val)
    return val

def _note_data_error(msg):
    _ERROR_NOTICE["count"] += 1
    now=time.time()
    if now-_ERROR_NOTICE["last"] >= ERROR_TG_COOLDOWN_SEC:
        _ERROR_NOTICE["last"]=now; _ERROR_NOTICE["active"]=True
        tg(f"E HIT & RUN — MARKET DATA WARNING ⚠️\n{str(msg)[:220]}\nAutomatic failover/retry is active. No Telegram spam for repeated errors.")

def _note_data_recovery():
    if _ERROR_NOTICE.get("active"):
        n=int(_ERROR_NOTICE.get("count",0))
        _ERROR_NOTICE.update({"active":False,"count":0,"last":time.time()})
        tg(f"E HIT & RUN — MARKET DATA RECOVERED ✅\nAPI access restored after {n} failed request(s).")

def _get(path, params=None, timeout=12, cache_ttl=0, allow_stale=False):
    params=params or {}
    key=(path, tuple(sorted((str(k),str(v)) for k,v in params.items())))
    if cache_ttl:
        cached=_cache_get(key, cache_ttl)
        if cached is not None: return cached

    last=None; now=time.time()
    bases=sorted(MARKET_ENDPOINTS, key=lambda b: (_ENDPOINT_HEALTH[b]["down_until"]>now, _ENDPOINT_HEALTH[b]["fails"]))
    for attempt in range(max(1,HTTP_RETRIES)):
        for base in bases:
            h=_ENDPOINT_HEALTH[base]
            if h["down_until"]>time.time():
                continue
            try:
                r=SESSION.get(base+path, params=params, timeout=timeout)
                if r.ok:
                    h["fails"]=0; h["down_until"]=0.0
                    val=r.json()
                    if cache_ttl: _cache_put(key,val)
                    _note_data_recovery()
                    return val
                last=f"{base} HTTP {r.status_code}: {r.text[:120]}"
                h["fails"]+=1
                if r.status_code in (418,429,500,502,503,504):
                    h["down_until"]=time.time()+ENDPOINT_COOLDOWN_SEC
            except Exception as e:
                last=f"{base}: {e}"
                h["fails"]+=1; h["down_until"]=time.time()+ENDPOINT_COOLDOWN_SEC
        if attempt < HTTP_RETRIES-1:
            time.sleep(HTTP_BACKOFF_BASE*(2**attempt)+random.uniform(0,0.25))
            now=time.time()
            bases=sorted(MARKET_ENDPOINTS, key=lambda b: (_ENDPOINT_HEALTH[b]["down_until"]>now, _ENDPOINT_HEALTH[b]["fails"]))

    if allow_stale and key in _HTTP_CACHE:
        return _HTTP_CACHE[key][1]
    _note_data_error(last or f"market request failed: {path}")
    raise RuntimeError(f"market request failed after failover: {last}")

def _tg_daily_pnl_suffix():
    """Return current UAE-day cumulative realized NET PnL for every Telegram message."""
    try:
        if STATE_PATH.exists():
            with open(STATE_PATH,"r",encoding="utf-8") as fh:
                st=json.load(fh)
            day=float(st.get("realized_day",0.0) or 0.0)
            d=str(st.get("realized_day_date",datetime.now(UAE).date().isoformat()))
            return f"\n\n📅 Daily cumulative NET PnL ({d} UAE): {day:+.2f} USDT"
    except Exception as ex:
        print("[E TELEGRAM DAILY PNL WARN]",str(ex)[:100])
    return "\n\n📅 Daily cumulative NET PnL: N/A"

def tg(text, reply_markup=None):
    if not TG_TOKEN or not TG_CHAT: return
    try:
        text=str(text)+_tg_daily_pnl_suffix()
        payload={"chat_id":TG_CHAT,"text":text[:4096]}
        if reply_markup:
            payload["reply_markup"]=json.dumps(reply_markup)
        r=requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                        data=payload, timeout=5)
        if not r.ok:
            print("[E TELEGRAM WARN]", r.status_code, str(r.text)[:140])
    except Exception as ex:
        print("[E TELEGRAM WARN]", str(ex)[:140])

def _tg_controls(p, *args, **kwargs):
    tid=str(p.get("trade_id",""))
    return {"inline_keyboard":[
        [{"text":"🔄 UPDATE","callback_data":f"{TG_CALLBACK_PREFIX}:UPDATE:{tid}"},
         {"text":"💰 SELL NOW","callback_data":f"{TG_CALLBACK_PREFIX}:SELL:{tid}"}],
        [{"text":"📊 STATUS","callback_data":f"{TG_CALLBACK_PREFIX}:STATUS:{tid}"},
         {"text":"📈 CHART","callback_data":f"{TG_CALLBACK_PREFIX}:CHART:{tid}"}],
        [{"text":"📈 CONTINUE","callback_data":f"{TG_CALLBACK_PREFIX}:CONTINUE:{tid}"},
         {"text":"🤖 AUTO","callback_data":f"{TG_CALLBACK_PREFIX}:AUTO:{tid}"}]
    ]}

def _tg_answer(callback_id, text):
    if not TG_TOKEN or not callback_id: return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/answerCallbackQuery",
                      data={"callback_query_id":callback_id,"text":text[:180]},timeout=4)
    except Exception:
        pass

def _route_badge(p):
    path=str(p.get("entry_path","HARMONIC")).upper()
    return {
        "HARMONIC": "🟣 HARMONIC",
        "EXCEPTIONAL_COIN": "🟡 EXCEPTIONAL COIN",
        "MAJOR_STRUCTURAL_BREAKOUT": "🔵 STRUCTURAL BREAKOUT",
    }.get(path, f"⚪ {path}")

def _route_short(p):
    return _route_badge(p)

def _tg_status_text(sym,p,px):
    entry=float(p.get("entry",0) or 0); qty=float(p.get("qty",0) or 0)
    tp1=float(p.get("tp1",0) or 0); tp2=float(p.get("tp2",0) or 0); tp3=float(p.get("tp3",0) or 0)
    tp4=float(p.get("tp4_extension",0) or 0)
    gross,costs,net=_e_estimated_net(p,px)
    mode=str(p.get("tp3plus_exit_mode","AUTO"))
    return (
        f"🟢 E | HIT & RUN | CONTROL STATUS | COST-PARITY\n{_route_badge(p)}\n{sym}\n"
        f"Price: {px:.8g}\nEntry: {entry:.8g}\nGross PnL: {gross:+.2f} USDT\nEst. Trading Cost: -{costs:.2f} USDT\nEst. NET PnL: {net:+.2f} USDT\n"
        f"{'✅' if p.get('tp1_hit') else '⬜'} TP1: {tp1:.8g}\n"
        f"{'✅' if p.get('tp2_hit') else '⬜'} TP2: {tp2:.8g}\n"
        f"{'✅' if p.get('tp3_milestone_notified') else '⬜'} TP3: {tp3:.8g}\n"
        f"{'✅' if p.get('tp4_milestone_notified') else '⬜'} TP4/Ext: {tp4:.8g}\n"
        f"High: {float(p.get('runner_high',p.get('peak_price',entry))):.8g}\n"
        f"Protected stop: {float(p.get('stop',0)):.8g}\n"
        f"Exit mode: {mode}\n"
        f"1m Smart Exit: {'ARMED' if mode=='AUTO' and p.get('tp3_milestone_notified') else 'PAUSED/MANUAL'}"
    )

def _target_profit(entry,target,qty):
    if entry<=0 or target<=0:
        return 0.0,0.0
    pct=(target/entry-1.0)*100.0
    usd=(target-entry)*qty
    return pct,usd

def _tg_target_dashboard(sym,p,px):
    entry=float(p.get("entry",0) or 0); qty=float(p.get("qty",0) or 0)
    targets=[("TP1",float(p.get("tp1",0) or 0),bool(p.get("tp1_hit"))),
             ("TP2",float(p.get("tp2",0) or 0),bool(p.get("tp2_hit"))),
             ("TP3",float(p.get("tp3",0) or 0),bool(p.get("tp3_milestone_notified"))),
             ("TP4/EXT",float(p.get("tp4_extension",0) or 0),bool(p.get("tp4_milestone_notified")))]
    rows=[]
    for label,target,hit in targets:
        pct,usd=_target_profit(entry,target,qty)
        rows.append(f"{'✅' if hit else '⬜'} {label}: {target:.8g} | {pct:+.2f}% | {usd:+.2f} USDT")
    curpct=(px/entry-1)*100 if entry else 0; gross,costs,net=_e_estimated_net(p,px)
    return (f"🟢 E | HIT & RUN | TARGET TRACKER | COST-PARITY\n{_route_badge(p)}\n{sym}\n"
            f"Entry: {entry:.8g}\\nCurrent: {px:.8g} | {curpct:+.2f}%\nGross: {gross:+.2f} | Est. Cost: -{costs:.2f} | Est. NET: {net:+.2f} USDT\n"+
            "\n".join(rows)+f"\nProtected Floor: {_active_profit_floor(p):.8g}\nMode: {p.get('tp3plus_exit_mode','AUTO')}")

def _tg_send_chart(sym,p):
    if not TG_TOKEN or not TG_CHAT:return
    try:
        px=price(sym); tp4=float(p.get("tp4_extension",0) or 0)
        path=build_entry_chart(sym,float(p["entry"]),float(p["stop"]),float(p["tp1"]),float(p["tp2"]),
                               float(p["tp3"]),{},tp4=tp4,current=px,protected_floor=_active_profit_floor(p))
        if not path:
            tg(_tg_target_dashboard(sym,p,px),reply_markup=_tg_controls(p)); return
        with open(path,"rb") as fh:
            payload={"chat_id":TG_CHAT,"caption":_tg_target_dashboard(sym,p,px),"reply_markup":json.dumps(_tg_controls(p))}
            r=requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto",data=payload,files={"photo":fh},timeout=15)
            if not r.ok: print("[E TELEGRAM CHART WARN]",r.status_code,str(r.text)[:140])
        try: os.remove(path)
        except Exception: pass
    except Exception as ex:
        print("[E TELEGRAM CHART WARN]",str(ex)[:140])

def process_telegram_callbacks(s):
    if not TG_CALLBACKS_ENABLED or not TG_TOKEN:return
    params={"timeout":0,"limit":50}
    if s.get("telegram_update_offset") is not None: params["offset"]=int(s["telegram_update_offset"])
    try:
        r=requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates",params=params,timeout=5)
        if not r.ok:
            if r.status_code==409:
                print("[E TELEGRAM CALLBACK WARN] 409 conflict: use dedicated E_TELEGRAM_BOT_TOKEN.")
            return
        updates=r.json().get("result",[])
    except Exception as ex:
        print("[E TELEGRAM CALLBACK WARN]",str(ex)[:120]); return
    changed=False
    for u in updates:
        s["telegram_update_offset"]=int(u.get("update_id",0))+1; changed=True
        cq=u.get("callback_query") or {}; data=str(cq.get("data",""))
        if not data.startswith(TG_CALLBACK_PREFIX+":"): continue
        parts=data.split(":",2); cid=cq.get("id")
        if len(parts)!=3: continue
        action,tid=parts[1],parts[2]; sym=None;p=None
        for k,v in list(s.get("positions",{}).items()):
            if str(v.get("trade_id",""))==tid:sym=k;p=v;break
        if not p:_tg_answer(cid,"Trade is no longer active.");continue
        try:px=price(sym)
        except Exception:px=float(p.get("entry",0) or 0)
        if action=="SELL":
            _tg_answer(cid,"Selling full position now.");close_position(s,sym,px,"USER_TELEGRAM_FULL_PROFIT_EXIT");continue
        if action=="AUTO":
            p["tp3plus_exit_mode"]="AUTO";save_state(s);_tg_answer(cid,"Auto management active.")
            tg(f"E HIT & RUN | AUTO 🤖\\n{sym}\\nTP3/TP4 profit floors remain active.",reply_markup=_tg_controls(p));continue
        if action=="CONTINUE":
            p["tp3plus_exit_mode"]="MANUAL_HOLD" if p.get("tp4_milestone_notified") else "HOLD_TO_TP4"
            save_state(s);_tg_answer(cid,"Continue selected.")
            tg(f"E HIT & RUN | CONTINUE 📈\\n{sym}\\nProfit floor remains mandatory.",reply_markup=_tg_controls(p));continue
        if action=="UPDATE":
            _tg_answer(cid,"Updated price and trade status.")
            tg(_tg_target_dashboard(sym,p,px)+"\n\n🔄 Updated now | SELL NOW remains available below.",reply_markup=_tg_controls(p));continue
        if action=="STATUS":
            _tg_answer(cid,"Status sent.");tg(_tg_target_dashboard(sym,p,px),reply_markup=_tg_controls(p));continue
        if action=="CHART":
            _tg_answer(cid,"Fresh chart sent.");_tg_send_chart(sym,p);continue
    if changed:save_state(s)


def tg_photo(path, caption="", reply_markup=None):
    """Send a chart image to Telegram without ever blocking trading if Telegram fails."""
    if not TG_TOKEN or not TG_CHAT: return
    try:
        caption=(str(caption)+_tg_daily_pnl_suffix())[:1024]
        with open(path,"rb") as fh:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto",
                          data={"chat_id":TG_CHAT,"caption":caption, **({"reply_markup": json.dumps(reply_markup)} if reply_markup else {})},
                          files={"photo":fh}, timeout=12)
    except Exception as e:
        print("[E CHART TELEGRAM WARN]", str(e)[:100])


def _chart_vwap(df, n=60):
    x=df.tail(n).copy()
    tp=(x.h+x.l+x.c)/3.0
    den=x.v.cumsum().replace(0,np.nan)
    return (tp*x.v).cumsum()/den


def _draw_candles(ax, df):
    """Minimal dependency candle renderer; matplotlib only, no mplfinance dependency."""
    x=df.reset_index(drop=True)
    width=0.55
    for i,row in x.iterrows():
        o,h,l,c=map(float,[row.o,row.h,row.l,row.c])
        up=c>=o
        col="#20a35a" if up else "#d84b4b"
        ax.vlines(i,l,h,color=col,linewidth=0.8,alpha=0.9)
        lo=min(o,c); height=max(abs(c-o), max(abs(c)*1e-6,1e-12))
        rect=None
        try:
            from matplotlib.patches import Rectangle
            rect=Rectangle((i-width/2,lo),width,height,facecolor=col,edgecolor=col,linewidth=0.6)
            ax.add_patch(rect)
        except Exception:
            pass
    ax.set_xlim(-1,len(x)+1)
    return x


def build_entry_chart(symbol, entry, stop, tp1, tp2, tp3, setup, tp4=None, current=None, protected_floor=None):
    """Telegram chart: E 5m/15m execution + governing model context, B-master layout."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        frames=[]
        for tf in ("5m","15m"):
            d=klines(symbol,tf,90).tail(60).copy()
            if len(d)<25: return None
            frames.append((tf,d))
        fig,axes=plt.subplots(2,1,figsize=(11,8),sharex=False)
        for ax,(tf,d) in zip(axes,frames):
            x=_draw_candles(ax,d)
            e9=ema(d.c,9).reset_index(drop=True)
            e21=ema(d.c,21).reset_index(drop=True)
            vw=_chart_vwap(d,60).reset_index(drop=True)
            ax.plot(range(len(x)),e9,linewidth=1.1,label="EMA9")
            ax.plot(range(len(x)),e21,linewidth=1.1,label="EMA21")
            ax.plot(range(len(x)),vw,linewidth=1.0,linestyle="--",label="VWAP")
            classical=setup.get("classical_assist",{}) or {}
            breakout=classical.get("breakout") if classical.get("valid") else None
            if breakout: ax.axhline(float(breakout),linewidth=1.0,linestyle="-.",label=f"BREAKOUT {float(breakout):.8g}")
            ax.axhline(entry,linewidth=1.2,label=f"ENTRY {entry:.8g}")
            ax.axhline(stop,linewidth=0.9,linestyle="--",label=f"SL {stop:.8g}")
            ax.axhline(tp1,linewidth=0.9,linestyle="--",label=f"TP1 {tp1:.8g}")
            ax.axhline(tp2,linewidth=0.9,linestyle="--",label=f"TP2 {tp2:.8g}")
            ax.axhline(tp3,linewidth=0.9,linestyle="--",label=f"TP3 {tp3:.8g}")
            if tp4 and float(tp4)>0: ax.axhline(float(tp4),linewidth=1.0,linestyle="-.",label="TP4/EXT")
            if current and float(current)>0: ax.axhline(float(current),linewidth=1.0,label="CURRENT")
            if protected_floor and float(protected_floor)>0: ax.axhline(float(protected_floor),linewidth=1.0,linestyle=":",label="PROFIT FLOOR")
            try:
                rv_tf=rsi(d.c)
                rvol=float(d.v.iloc[-3:].mean()/max(float(d.v.iloc[-30:-3].mean()),1e-12))
                ax.set_title(f"{symbol} | {tf} | RSI {rv_tf:.1f} | RVOL {rvol:.2f}")
            except Exception:
                ax.set_title(f"{symbol} | {tf}")
            ax.grid(alpha=0.18)
            ax.legend(loc="upper left",fontsize=7,ncol=7)
        harm=setup.get("harmonic_assist",{}) or {}
        classical=setup.get("classical_assist",{}) or {}
        model=str(setup.get("_telegram_model_name") or harm.get("name") or "15M MODEL")
        path=str(setup.get("_telegram_entry_path") or "HARMONIC")
        fig.suptitle(
            f"E HIT & RUN {path} | {symbol} | MODEL: {model}\n"
            f"ENTRY {entry:.8g} | SL {stop:.8g} | TP1 {tp1:.8g} | TP2 {tp2:.8g} | TP3 {tp3:.8g}",
            fontsize=11)
        fig.tight_layout(rect=(0,0,1,0.94))
        path=f"/tmp/E_{symbol}_{int(time.time())}_5m15m.png"
        fig.savefig(path,dpi=135,bbox_inches="tight")
        plt.close(fig)
        return path
    except Exception as e:
        print("[E CHART WARN]", symbol, str(e)[:120])
        return None


def send_entry_recommendation_chart(symbol, p, setup, risk, rr):
    harm=setup.get("harmonic_assist",{}) or {}
    classical=setup.get("classical_assist",{}) or {}
    st=setup.get("structure_state",{}) or {}
    path=p.get("entry_path","HARMONIC"); model=p.get("model_name",harm.get("name",""))
    tp1=float(p.get("tp1",0)); tp2=float(p.get("tp2",0)); tp3=float(p.get("tp3",0)); tp4=float(p.get("tp4_extension",0) or 0)
    notional=float(p.get("notional",0) or 0); entry=float(p["entry"]); qty=float(p["qty"])
    def row(name,v):
        pct=(v/entry-1)*100; usd=(v-entry)*qty
        return f"{name}: {v:.8g} | {pct:+.2f}% | ${usd:+.2f}"
    caption=(
        f"🟢 E | HIT & RUN | OPEN\n{_route_badge(p)}\n{symbol}\n"
        f"Model: {model}\nExecution: ${notional:.2f}\n"
        f"Entry: {entry:.8g}\nEntry Fee: -${float(p.get('entry_fee_usdt',0)):.2f} | Entry Slippage: -${float(p.get('entry_slippage_usdt',0)):.2f}\n"
        f"Est. Round-trip Cost: -${(_e_estimated_net(p,entry)[1]):.2f}\n"
        f"SL: {p['stop']:.8g} | Risk ${risk:.2f}\n"
        f"{row('TP1',tp1)}\n{row('TP2',tp2)}\n{row('TP3',tp3)}\n{row('TP4',tp4)}\n"
        f"R:R TP3: {rr:.2f} | Confirm: {float(st.get('confirm_score',0) or 0):.0f}\n"
        f"Execution frame: 1m fast confirmation\n"
        f"Management frame: 15m | Model/Wave targets\n"
        "Chart: 5m / 15m | breakout/model + ENTRY + SL + TP1-TP4 shown"
    )
    base=symbol.upper().replace("USDT","")
    buttons=_tg_controls(p)
    buttons["inline_keyboard"].append([
        {"text":"Binance","url":f"https://www.binance.com/en/trade/{base}_USDT"},
        {"text":"TradingView","url":f"https://www.tradingview.com/chart/?symbol=BINANCE%3A{symbol}"}
    ])
    setup=dict(setup); setup["_telegram_entry_path"]=path; setup["_telegram_model_name"]=model
    path_img=build_entry_chart(symbol,entry,p['stop'],tp1,tp2,tp3,setup,tp4=tp4,current=entry,protected_floor=p['stop'])
    if path_img:
        tg_photo(path_img,caption,buttons)
        try: os.remove(path_img)
        except Exception: pass
    else:
        tg(caption)

def _json_safe(v, _seen=None, _depth=0):
    """Cycle/depth-safe JSON sanitizer. Prevents telemetry payloads from crashing the trading loop."""
    if _seen is None: _seen=set()
    if _depth > 24: return "<MAX_DEPTH>"
    if isinstance(v, np.generic): v=v.item()
    if isinstance(v, float): return v if math.isfinite(v) else None
    if v is None or isinstance(v,(str,int,bool)): return v
    if isinstance(v,(dict,list,tuple,set)):
        oid=id(v)
        if oid in _seen: return "<CYCLE>"
        _seen.add(oid)
        try:
            if isinstance(v,dict): return {str(k):_json_safe(x,_seen,_depth+1) for k,x in v.items()}
            return [_json_safe(x,_seen,_depth+1) for x in v]
        finally:
            _seen.discard(oid)
    return str(v)

def _hub(path, payload):
    if not AGENTIC_HUB_URL: return
    payload=_json_safe(payload)
    def go():
        try:
            h={"X-Agentic-Key":AGENTIC_HUB_KEY} if AGENTIC_HUB_KEY else {}
            r=requests.post(AGENTIC_HUB_URL+path,json=payload,headers=h,timeout=4)
            if not r.ok: print("[AGENTIC HTTP WARN]", path, r.status_code, str(r.text)[:120])
        except Exception as e: print("[AGENTIC WARN]", str(e)[:120])
    threading.Thread(target=go,daemon=True).start()

def emit(event, symbol="", trade_id="", score=None, reason="", payload=None):
    p=dict(payload or {})
    p.setdefault("schema_version","2.1")
    p.setdefault("strategy_name",STRATEGY_NAME)
    _hub("/event", {"strategy":STRATEGY_CODE,"event":event,"symbol":symbol,"trade_id":trade_id,
                    "score":float(score) if score is not None else None,"reason":reason,
                    "payload":p,"ts_uae":now_uae()})

def default_state():
    return {"engine_id":ENGINE_ID,"strategy_cash":NOMINAL_CAPITAL,"initial_capital":NOMINAL_CAPITAL,
            "realized_total":0.0,"realized_day":0.0,"realized_day_date":datetime.now(UAE).date().isoformat(),
            "positions":{},"closed":[],"cooldown":{},"failed_setups":{},"created":now_uae()}

def load_state():
    try:
        if STATE_PATH.exists():
            s=json.loads(STATE_PATH.read_text())
            s.setdefault("positions",{}); s.setdefault("closed",[]); s.setdefault("cooldown",{}); s.setdefault("failed_setups",{})
            return s
    except Exception as e: print("[STATE WARN]",e)
    return default_state()

def save_state(s):
    """Atomic, cycle-safe state persistence. Telemetry objects can never kill the trading loop."""
    STATE_PATH.parent.mkdir(parents=True,exist_ok=True)
    tmp=STATE_PATH.with_suffix(".tmp")
    clean=_json_safe(s)
    if not isinstance(clean,dict):
        raise TypeError("STATE_SANITIZER_DID_NOT_RETURN_DICT")
    tmp.write_text(json.dumps(clean,indent=2,allow_nan=False))
    tmp.replace(STATE_PATH)

def price(symbol):
    try:
        px=float(_get("/api/v3/ticker/price",{"symbol":symbol}, cache_ttl=2)["price"])
        _LAST_PRICE[symbol]=(time.time(),px)
        return px
    except Exception:
        row=_LAST_PRICE.get(symbol)
        if row and time.time()-row[0] <= PRICE_STALE_SEC:
            return float(row[1])
        raise

def klines(symbol, interval, limit):
    raw=_get("/api/v3/klines",{"symbol":symbol,"interval":interval,"limit":limit})
    d=pd.DataFrame(raw,columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","x"])
    for c in ["o","h","l","c","v","qv"]: d[c]=pd.to_numeric(d[c],errors="coerce")
    return d.iloc[:-1].copy() if len(d)>2 else d

def atr(df,n=14):
    pc=df.c.shift(1); tr=pd.concat([(df.h-df.l).abs(),(df.h-pc).abs(),(df.l-pc).abs()],axis=1).max(axis=1)
    return float(tr.rolling(n).mean().iloc[-1])

def rsi(s,n=14):
    d=s.diff(); up=d.clip(lower=0).rolling(n).mean(); dn=(-d.clip(upper=0)).rolling(n).mean()
    rs=up/(dn.replace(0,np.nan)); return float((100-100/(1+rs)).iloc[-1])

def ema(s,n): return s.ewm(span=n,adjust=False).mean()

def pac(df, n=10):
    """Price Action Channel: EMA(high/low/close), adapted from the supplied Scalping Swing tool."""
    return ema(df.h,n), ema(df.l,n), ema(df.c,n)

def confirmed_fractals(df):
    """Confirmed 5-bar fractal pivots only (no look-ahead in live use). Returns recent highs/lows."""
    highs=[]; lows=[]
    h=df.h.to_numpy(); l=df.l.to_numpy()
    # A center pivot at i is only known once i+2 has closed.
    for i in range(2, len(df)-2):
        if h[i]>h[i-1] and h[i]>h[i-2] and h[i]>h[i+1] and h[i]>h[i+2]: highs.append((i,float(h[i])))
        if l[i]<l[i-1] and l[i]<l[i-2] and l[i]<l[i+1] and l[i]<l[i+2]: lows.append((i,float(l[i])))
    return highs[-6:], lows[-6:]

def structure_state(df):
    """Compact HH/HL/LH/LL structure from confirmed fractals."""
    ph, pl = confirmed_fractals(df)
    last_highs=[x[1] for x in ph[-3:]]; last_lows=[x[1] for x in pl[-3:]]
    hh = len(last_highs)>=2 and last_highs[-1] > last_highs[-2]
    lh = len(last_highs)>=2 and last_highs[-1] < last_highs[-2]
    hl = len(last_lows)>=2 and last_lows[-1] > last_lows[-2]
    ll = len(last_lows)>=2 and last_lows[-1] < last_lows[-2]
    return {"hh":hh,"hl":hl,"lh":lh,"ll":ll,
            "pivot_high":last_highs[-1] if last_highs else None,
            "pivot_low":last_lows[-1] if last_lows else None}

def universe():
    ex=_get("/api/v3/exchangeInfo", cache_ttl=EXCHANGEINFO_CACHE_SEC, allow_stale=True)
    eligible={x["symbol"] for x in ex["symbols"] if x.get("status")=="TRADING" and x.get("quoteAsset")=="USDT" and x.get("isSpotTradingAllowed",True)}
    tick=_get("/api/v3/ticker/24hr", cache_ttl=TICKER24_CACHE_SEC, allow_stale=True)
    rows=[]
    for x in tick:
        sym=x.get("symbol","")
        if sym not in eligible: continue
        qv=float(x.get("quoteVolume",0) or 0)
        if qv < MIN_QUOTE_VOLUME: continue
        ch=abs(float(x.get("priceChangePercent",0) or 0))
        rows.append((sym,qv,ch))
    rows.sort(key=lambda z:(z[1],z[2]),reverse=True)
    return [x[0] for x in rows[:SCAN_LIMIT]]

def session_vwap(df, bars=48):
    """Rolling intraday VWAP from closed candles."""
    x=df.iloc[-bars:].copy()
    tp=(x.h+x.l+x.c)/3.0
    return float((tp*x.v).sum()/max(float(x.v.sum()),1e-12))

def volume_profile(df, bars=72, bins=24):
    """Candle-volume approximation of Volume Profile: POC, VAH, VAL and nearest HVN/LVN context."""
    x=df.iloc[-bars:].copy()
    lo=float(x.l.min()); hi=float(x.h.max())
    if hi<=lo: return {"poc":float(x.c.iloc[-1]),"vah":hi,"val":lo,"hvn":hi,"lvn":lo}
    edges=np.linspace(lo,hi,bins+1); hist=np.zeros(bins,dtype=float)
    typical=((x.h+x.l+x.c)/3.0).to_numpy(); vols=x.v.to_numpy()
    idx=np.clip(np.digitize(typical,edges)-1,0,bins-1)
    for i,v in zip(idx,vols): hist[int(i)]+=float(v)
    centers=(edges[:-1]+edges[1:])/2
    poc_i=int(np.argmax(hist)); total=float(hist.sum())
    order=np.argsort(hist)[::-1]; chosen=[]; acc=0.0
    for i in order:
        chosen.append(int(i)); acc+=float(hist[i])
        if total<=0 or acc>=0.70*total: break
    val=float(edges[min(chosen)]) if chosen else lo
    vah=float(edges[max(chosen)+1]) if chosen else hi
    hvn=float(centers[poc_i])
    nz=np.where(hist>0)[0]
    lvn=float(centers[int(nz[np.argmin(hist[nz])])]) if len(nz) else lo
    return {"poc":float(centers[poc_i]),"vah":vah,"val":val,"hvn":hvn,"lvn":lvn}

def market_regime():
    """Light market context: BTC 5m/15m + broad 24h USDT breadth. Never a total trading shutdown."""
    try:
        b5=klines("BTCUSDT","5m",60); b15=klines("BTCUSDT","15m",60)
        btc5=(float(b5.c.iloc[-1])/float(b5.c.iloc[-4])-1)*100
        btc15=(float(b15.c.iloc[-1])/float(b15.c.iloc[-4])-1)*100
        tick=_get("/api/v3/ticker/24hr", cache_ttl=TICKER24_CACHE_SEC, allow_stale=True)
        changes=[]
        for x in tick:
            sym=x.get("symbol","")
            if not sym.endswith("USDT"): continue
            qv=float(x.get("quoteVolume",0) or 0)
            if qv<MIN_QUOTE_VOLUME: continue
            changes.append(float(x.get("priceChangePercent",0) or 0))
        breadth=(sum(1 for z in changes if z>0)/max(len(changes),1))*100
        if btc5>0.15 and btc15>0 and breadth>=55: mode="GREEN"
        elif btc5<-0.20 and btc15<0 and breadth<45: mode="RED"
        else: mode="YELLOW"
        pts=5.0 if mode=="GREEN" else (3.0 if mode=="YELLOW" else 1.0)
        return {"mode":mode,"points":pts,"btc5":btc5,"btc15":btc15,"breadth":breadth}
    except Exception:
        return {"mode":"YELLOW","points":3.0,"btc5":0.0,"btc15":0.0,"breadth":50.0}



# -----------------------------------------------------------------------------
# V15 — Exceptional Coin + Multi-Timeframe Structural Breakout layer (E pilot)
# Independent from Harmonic. It does NOT re-enable Classical pattern entries.
# Decision frame: 1h / synthetic 3h / 4h / 1d / 1w structure.
# Execution timing: CLOSED 1m StochRSI + positive candle.
# -----------------------------------------------------------------------------
ECM_YELLOW_MIN = float(os.getenv("E_ECM_YELLOW_MIN", "82"))
ECM_RED_MIN = float(os.getenv("E_ECM_RED_MIN", "90"))
STRUCT_GREEN_MIN = float(os.getenv("E_STRUCT_GREEN_MIN", "75"))
STRUCT_YELLOW_MIN = float(os.getenv("E_STRUCT_YELLOW_MIN", "82"))
STRUCT_RED_MIN = float(os.getenv("E_STRUCT_RED_MIN", "88"))
ECM_MIN_RVOL = float(os.getenv("E_ECM_MIN_RVOL", "1.35"))
ECM_RED_MIN_RVOL = float(os.getenv("E_ECM_RED_MIN_RVOL", "1.80"))


def _resample_3h(d1h):
    try:
        x=d1h.copy()
        # Binance klines() returns closed candles. Build consecutive closed 3h bars without relying on timezone index.
        n=(len(x)//3)*3
        x=x.iloc[-n:].copy()
        rows=[]
        for i in range(0,len(x),3):
            q=x.iloc[i:i+3]
            rows.append({"o":float(q.o.iloc[0]),"h":float(q.h.max()),"l":float(q.l.min()),"c":float(q.c.iloc[-1]),"v":float(q.v.sum()),"qv":float(q.qv.sum()) if "qv" in q else 0.0})
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


def _pivot_highs(df, w=2):
    out=[]
    if df is None or len(df)<10: return out
    h=df.h.astype(float).reset_index(drop=True)
    for i in range(w,len(h)-w):
        if float(h.iloc[i]) >= float(h.iloc[i-w:i+w+1].max()): out.append((i,float(h.iloc[i])))
    return out


def _frame_breakout(df, live_price, name):
    """Detect previous-candle high, repeated horizontal resistance and descending major trendline breaks."""
    empty={"frame":name,"score":0.0,"breaks":[],"level":None,"strength":0.0}
    try:
        if df is None or len(df)<12: return empty
        x=df.tail(90).reset_index(drop=True); px=float(live_price); prev_close=float(x.c.iloc[-1])
        av=max(float(atr(x,14)), px*0.002)
        breaks=[]; levels=[]; score=0.0
        # 1) Break above the high of the latest fully closed candle on this frame.
        prev_high=float(x.h.iloc[-1])
        if px > prev_high*1.0005:
            breaks.append("PREVIOUS_CANDLE_HIGH"); levels.append(prev_high); score+=20.0
        # 2) Horizontal resistance: 20/60-bar highs, stronger when the level has repeated touches.
        for look,pts,label in ((20,22.0,"HORIZONTAL_20"),(60,28.0,"HISTORICAL_60")):
            if len(x)>=look:
                z=x.iloc[-look:]
                lvl=float(z.h.max())
                tol=max(0.003*lvl,0.35*av)
                touches=int(((z.h.astype(float)-lvl).abs()<=tol).sum())
                if px > lvl*1.001 and touches>=2:
                    breaks.append(label); levels.append(lvl); score+=pts + min(8.0,(touches-2)*2.0)
        # 3) Descending trendline projected from the last two confirmed pivot highs.
        ph=_pivot_highs(x,2)
        if len(ph)>=2:
            (i1,h1),(i2,h2)=ph[-2],ph[-1]
            if i2>i1 and h2<h1:
                slope=(h2-h1)/(i2-i1)
                projected=h2+slope*((len(x)-1)-i2)
                # live price must clear the projected line; last closed frame should not already be far above it.
                if px > projected*1.002 and prev_close <= projected*1.01:
                    breaks.append("DESCENDING_TRENDLINE"); levels.append(projected); score+=32.0
        strength=min(100.0,score)
        return {"frame":name,"score":round(score,1),"breaks":breaks,"level":max(levels) if levels else None,"strength":round(strength,1)}
    except Exception as ex:
        return {**empty,"error":str(ex)[:100]}


def exceptional_structural_assist(symbol, d1h, live_price, vol_ratio, ret5, ret15, regime, est_daily_qv, late_chase):
    """Separate coin strength from market strength. HTF structure decides WHAT; 1m later decides WHEN."""
    px=float(live_price)
    try:
        btc15=float((regime or {}).get("btc15",0.0) or 0.0)
        rel15=float(ret15)-btc15
        # Cheap first pass. A coin must show some independent impulse or 1h pressure before extra HTF API work.
        one=_frame_breakout(d1h,px,"1h")
        prelim=bool(one.get("breaks") or vol_ratio>=1.20 or ret5>=0.35 or ret15>=0.65 or rel15>=0.75)
        if not prelim:
            return {"eligible":False,"exceptional":False,"score":0.0,"structural_score":float(one.get("score",0)),"frames":{"1h":one},"reason":"NO_INDEPENDENT_IMPULSE"}
        d3h=_resample_3h(d1h)
        d4h=klines(symbol,"4h",120)
        d1d=klines(symbol,"1d",100)
        d1w=klines(symbol,"1w",80)
        frames={"1h":one,"3h":_frame_breakout(d3h,px,"3h"),"4h":_frame_breakout(d4h,px,"4h"),"1d":_frame_breakout(d1d,px,"1d"),"1w":_frame_breakout(d1w,px,"1w")}
        active=[v for v in frames.values() if v.get("breaks")]
        frame_count=len(active)
        strongest=max([float(v.get("score",0)) for v in frames.values()] or [0.0])
        multi_bonus=min(24.0,max(0,frame_count-1)*6.0)
        structural=min(100.0,strongest+multi_bonus)
        # Individual coin score: independent acceleration + volume + HTF structural evidence + liquidity.
        vol_pts=min(30.0,max(0.0,(float(vol_ratio)-1.0)*22.0))
        accel_pts=min(22.0,max(0.0,float(ret5)*5.0)+max(0.0,float(ret15))*2.0)
        rel_pts=min(18.0,max(0.0,rel15)*8.0)
        struct_pts=0.30*structural
        liq_pts=10.0 if float(est_daily_qv)>=MIN_QUOTE_VOLUME*8 else (6.0 if float(est_daily_qv)>=MIN_QUOTE_VOLUME*4 else 2.0)
        score=min(100.0,vol_pts+accel_pts+rel_pts+struct_pts+liq_pts)
        exceptional=bool(score>=ECM_YELLOW_MIN and float(vol_ratio)>=ECM_MIN_RVOL and structural>=STRUCT_YELLOW_MIN and not late_chase)
        # V15.1: HTF structure is a LOCATOR, not a late execution gate.
        # A major historical/trendline breakout is an independent OR path even before ECM reaches an extreme score.
        major_labels={"HISTORICAL_60","DESCENDING_TRENDLINE"}
        major_break=any(any(lbl in major_labels for lbl in (v.get("breaks") or [])) for v in active)
        structural_signal=bool(active and (major_break or frame_count>=2 or strongest>=28.0) and not late_chase)
        mode=str((regime or {}).get("mode","YELLOW")).upper()
        if mode=="RED":
            # RED still needs evidence of independence, but no longer demands an ultra-high ECM score.
            structural_pass=bool(structural_signal and structural>=32.0 and (float(vol_ratio)>=1.10 or rel15>=0.50))
            eligible=bool(exceptional or structural_pass)
        else:
            # GREEN/YELLOW: confirmed major HTF structure OR exceptional coin can proceed to 1m execution timing.
            eligible=bool(exceptional or structural_signal)
        levels=[float(v["level"]) for v in active if v.get("level")]
        governing=max(levels) if levels else None
        route=("EXCEPTIONAL_COIN" if exceptional else ("MAJOR_STRUCTURAL_BREAKOUT" if structural_signal else "WATCH"))
        return {"eligible":eligible,"exceptional":exceptional,"structural_signal":structural_signal,"route":route,
                "score":round(score,1),"structural_score":round(structural,1),
                "relative_strength_15m":round(rel15,2),"rvol":round(float(vol_ratio),2),"frame_count":frame_count,
                "frames":frames,"governing_level":governing,"reason":"STRUCTURAL_OR_EXCEPTION_READY" if eligible else "STRUCTURAL_EXCEPTION_WATCH"}
    except Exception as ex:
        return {"eligible":False,"exceptional":False,"score":0.0,"structural_score":0.0,"frames":{},"reason":"STRUCTURAL_ASSIST_ERROR","error":str(ex)[:120]}


# === V16.0 15M MODEL INTELLIGENCE ==================================================
# 15m owns model discovery, structural context, wave map and targets.
# 1m is execution timing only. Classical patterns are context for STRUCTURAL path,
# never a fourth entry path.

def _compress_alternating_pivots(df, w=3, lookback=180):
    x=df.tail(lookback).reset_index(drop=True); raw=[]
    for i in range(w,len(x)-w):
        lo=float(x.l.iloc[i]); hi=float(x.h.iloc[i])
        if lo<=float(x.l.iloc[i-w:i+w+1].min()): raw.append((i,lo,'L'))
        if hi>=float(x.h.iloc[i-w:i+w+1].max()): raw.append((i,hi,'H'))
    raw.sort(key=lambda z:z[0]); out=[]
    for q in raw:
        if out and out[-1][2]==q[2]:
            if (q[2]=='L' and q[1]<out[-1][1]) or (q[2]=='H' and q[1]>out[-1][1]): out[-1]=q
        else: out.append(q)
    return x,out

def harmonic_scan_15m(d15, live_price):
    """V16.9 STRICT 5m harmonic scanner with dedicated family geometry.

    Canonical XABCD validators: Gartley, Bat, Butterfly, Crab, Deep Crab.
    Dedicated non-generic validators:
      - Cypher: B=0.382-0.618 XA, C=1.272-1.414 XA beyond A, D=0.786 XC.
      - Shark: OXABC geometry, A retraces OX, B=1.13-1.618 XA extension,
               C=1.618-2.24 AB extension and C converges at 0.886-1.13 OX.
    No 3-of-4 rescue. A pattern is valid only when ALL defining rules pass.
    """
    empty={"name":"None","direction":"NONE","confidence":0.0,"prz_low":None,"prz_high":None,
           "stop":None,"targets":[],"location":"NONE","long_alignment":False,
           "bearish_conflict":False,"ratios":{},"source_frame":"5m","strict_valid":False,
           "validation":{},"scanner_version":"STRICT_5M_V16.9_7PATTERN_FORENSIC"}
    try:
        x,piv=_compress_alternating_pivots(d15,3,220)
        if len(piv)<5:return empty

        defs={
          "Gartley":{"B":(.588,.648),"C":(.382,.886),"BCP":(1.13,1.618),"D":(.756,.816),"ABCD":(.95,1.05),"d_ideal":.786},
          "Bat":{"B":(.382,.55),"C":(.382,.886),"BCP":(1.618,2.618),"D":(.856,.916),"ABCD":(.95,1.35),"d_ideal":.886},
          "Butterfly":{"B":(.756,.816),"C":(.382,.886),"BCP":(1.55,2.618),"D":(1.232,1.308),"ABCD":(.95,1.35),"d_ideal":1.27},
          "Crab":{"B":(.382,.618),"C":(.382,.886),"BCP":(2.24,3.618),"D":(1.57,1.666),"ABCD":(.95,1.70),"d_ideal":1.618},
          "Deep Crab":{"B":(.856,.93),"C":(.382,.886),"BCP":(2.00,3.618),"D":(1.57,1.666),"ABCD":(.95,1.70),"d_ideal":1.618},
        }
        candidates=[]

        def closeness(v,lo,hi,ideal=None):
            if ideal is None: ideal=(lo+hi)/2
            scale=max(hi-lo,1e-9)
            return max(0.0,1.0-abs(v-ideal)/scale)

        for j in range(max(0,len(piv)-16),len(piv)-4):
            pts=piv[j:j+5]; types=[q[2] for q in pts]; pr=[float(q[1]) for q in pts]
            bull=types==['L','H','L','H','L']; bear=types==['H','L','H','L','H']
            if not (bull or bear):continue
            P0,P1,P2,P3,P4=pr

            # ----- Canonical XABCD families -----
            X,A,B,C,D=P0,P1,P2,P3,P4
            XA=(A-X) if bull else (X-A); AB=(A-B) if bull else (B-A)
            BC=(C-B) if bull else (B-C); CD=(C-D) if bull else (D-C)
            AD=(A-D) if bull else (D-A)
            if min(XA,AB,BC,CD)>1e-12:
                vals={"AB_XA":AB/XA,"BC_AB":BC/AB,"CD_BC":CD/BC,"AD_XA":AD/XA,"CD_AB":CD/AB}
                for name,r in defs.items():
                    checks={"B":r["B"][0]<=vals["AB_XA"]<=r["B"][1],
                            "C":r["C"][0]<=vals["BC_AB"]<=r["C"][1],
                            "BC_projection":r["BCP"][0]<=vals["CD_BC"]<=r["BCP"][1],
                            "D_XA":r["D"][0]<=vals["AD_XA"]<=r["D"][1],
                            "ABCD":r["ABCD"][0]<=vals["CD_AB"]<=r["ABCD"][1]}
                    if not all(checks.values()):continue
                    sane=(D>X if bull else D<X) if name in ("Gartley","Bat") else (D<X if bull else D>X)
                    if not sane:continue
                    precision=[closeness(vals["AB_XA"],*r["B"]),closeness(vals["BC_AB"],*r["C"]),
                               closeness(vals["CD_BC"],*r["BCP"]),closeness(vals["AD_XA"],*r["D"],r["d_ideal"]),
                               closeness(vals["CD_AB"],*r["ABCD"])]
                    recency=(pts[-1][0]+1)/max(len(x),1)
                    conf=(0.85+0.15*recency)*(0.80+0.20*sum(precision)/len(precision))
                    xa=abs(A-X); ideal_d=(A-r["d_ideal"]*xa) if bull else (A+r["d_ideal"]*xa)
                    candidates.append((conf,name,bull,pts,vals,checks,ideal_d,"XABCD"))

            # ----- Dedicated Cypher validator -----
            # Same alternating five pivots, but C MUST extend beyond A and D is measured from XC.
            XAabs=abs(P1-P0); XCabs=abs(P3-P0)
            if XAabs>1e-12 and XCabs>1e-12:
                b_ratio=abs(P1-P2)/XAabs
                c_xa=abs(P3-P0)/XAabs
                d_xc=abs(P3-P4)/XCabs
                cy_geom=(P3>P1 and P4>P0 and P4<P3) if bull else (P3<P1 and P4<P0 and P4>P3)
                cy_checks={"B_XA":.382<=b_ratio<=.618,"C_XA_EXTENSION":1.272<=c_xa<=1.414,
                           "D_XC_0786":.756<=d_xc<=.816,"C_BEYOND_A_D_INSIDE_XC":cy_geom}
                if all(cy_checks.values()):
                    ideal_d=(P3-.786*XCabs) if bull else (P3+.786*XCabs)
                    precision=[closeness(b_ratio,.382,.618),closeness(c_xa,1.272,1.414),closeness(d_xc,.756,.816,.786)]
                    recency=(pts[-1][0]+1)/max(len(x),1)
                    conf=(0.86+0.14*recency)*(0.82+0.18*sum(precision)/len(precision))
                    vals={"B_XA":b_ratio,"C_XA_EXTENSION":c_xa,"D_XC":d_xc}
                    candidates.append((conf,"Cypher",bull,pts,vals,cy_checks,ideal_d,"CYPHER_XC"))

            # ----- Dedicated Shark OXABC validator -----
            # Re-label the five pivots O,X,A,B,C. Completion is C, not a generic D.
            O,Xs,As,Bs,Cs=P0,P1,P2,P3,P4
            OX=abs(Xs-O); XA_s=abs(As-Xs); AB_s=abs(Bs-As)
            if min(OX,XA_s,AB_s)>1e-12:
                a_ox=abs(As-O)/OX
                b_xa=abs(Bs-As)/XA_s
                c_ab=abs(Cs-Bs)/AB_s
                c_ox=abs(Cs-O)/OX
                shark_geom=(Bs>Xs and Cs<Bs) if bull else (Bs<Xs and Cs>Bs)
                sh_checks={"A_OX":.382<=a_ox<=.618,"B_XA_EXTENSION":1.13<=b_xa<=1.618,
                           "C_AB_EXTENSION":1.618<=c_ab<=2.24,"C_OX_PRZ":.886<=c_ox<=1.13,
                           "B_BEYOND_X":shark_geom}
                if all(sh_checks.values()):
                    # C is the Shark completion. Ideal PRZ center favors the minimum 0.886 OX test;
                    # observed C must also satisfy the AB-extension convergence above.
                    if bull:
                        ideal_c=O-.886*OX if Cs<O else O+.886*OX
                    else:
                        ideal_c=O+.886*OX if Cs>O else O-.886*OX
                    precision=[closeness(a_ox,.382,.618),closeness(b_xa,1.13,1.618),
                               closeness(c_ab,1.618,2.24),closeness(c_ox,.886,1.13,.886)]
                    recency=(pts[-1][0]+1)/max(len(x),1)
                    conf=(0.86+0.14*recency)*(0.82+0.18*sum(precision)/len(precision))
                    vals={"A_OX":a_ox,"B_XA_EXTENSION":b_xa,"C_AB_EXTENSION":c_ab,"C_OX":c_ox}
                    candidates.append((conf,"Shark",bull,pts,vals,sh_checks,ideal_c,"SHARK_OXABC"))

        if not candidates:return empty
        conf,name,bull,pts,vals,checks,ideal_terminal,geometry=max(candidates,key=lambda z:z[0])
        terminal=float(pts[-1][1]); av=max(float(atr(x,14)),float(live_price)*0.0015)
        span=abs(float(pts[1][1])-float(pts[0][1]))
        half=max(.18*av,.012*max(span,1e-12))
        low=min(terminal,ideal_terminal)-half; high=max(terminal,ideal_terminal)+half; px=float(live_price)
        if low<=px<=high:loc='IN_PRZ';dist=0.0
        elif bull and px>high:dist=(px-high)/av;loc='RETEST' if dist<=HARMONIC_RETEST_ATR else 'ABOVE_PRZ'
        elif bull:dist=(low-px)/av;loc='BELOW_PRZ'
        elif (not bull) and px<low:dist=(low-px)/av;loc='RETEST' if dist<=HARMONIC_RETEST_ATR else 'BELOW_PRZ'
        else:dist=(px-high)/av;loc='ABOVE_PRZ'

        # Pattern-aware post-completion management targets.
        if name=="Cypher":
            C=float(pts[3][1]); D=terminal; leg=abs(C-D)
            if bull: candidates_t=[D+.382*leg,D+.618*leg,C]
            else: candidates_t=[D-.382*leg,D-.618*leg,C]
        elif name=="Shark":
            B=float(pts[3][1]); C=terminal; leg=abs(B-C)
            if bull: candidates_t=[C+.382*leg,C+.50*leg,C+.618*leg,B]
            else: candidates_t=[C-.382*leg,C-.50*leg,C-.618*leg,B]
        else:
            A=float(pts[1][1]); B=float(pts[2][1]); C=float(pts[3][1]); D=terminal
            if bull:candidates_t=[D+.382*abs(A-D),D+.618*abs(A-D),B,C,A]
            else:candidates_t=[D-.382*abs(A-D),D-.618*abs(A-D),B,C,A]
        if bull:
            stop=min(terminal,low)-.35*av; targets=sorted({float(z) for z in candidates_t if float(z)>terminal})
        else:
            stop=max(terminal,high)+.35*av; targets=sorted({float(z) for z in candidates_t if float(z)<terminal},reverse=True)

        long_align=bool(bull and conf>=HARMONIC_MIN_CONF and loc in ('IN_PRZ','RETEST'))
        bear_conf=bool((not bull) and conf>=HARMONIC_MIN_CONF and loc in ('IN_PRZ','RETEST'))
        return {"name":name,"direction":"BULLISH" if bull else "BEARISH","confidence":round(conf,4),
                "prz_low":low,"prz_high":high,"prz_ideal_terminal":ideal_terminal,"stop":stop,"targets":targets,
                "location":loc,"dist_prz_atr":round(dist,4),"long_alignment":long_align,
                "bearish_conflict":bear_conf,"ratios":vals,"points":pts,"source_frame":"5m",
                "strict_valid":True,"validation":checks,"geometry":geometry,
                "scanner_version":"STRICT_5M_V16.9_7PATTERN_FORENSIC"}
    except Exception as ex:return {**empty,"error":str(ex)[:160]}

def _harmonic_forensic_line(symbol, h):
    """Audit-only: expose strict 5m geometry/ratios/PRZ. Never gates an entry."""
    try:
        if not h or not h.get("strict_valid") or h.get("name") in (None,"None"):
            return
        pts=h.get("points") or []
        labels=("O","X","A","B","C") if h.get("name")=="Shark" else ("X","A","B","C","D")
        pv={}
        for lab,q in zip(labels,pts):
            try: pv[lab]=float(q[1])
            except Exception: pass
        ratios=h.get("ratios") or {}; checks=h.get("validation") or {}
        failed=[k for k,v in checks.items() if not v]
        print(f"[E V16.9 HARMONIC FORENSIC] {symbol} pattern={h.get('name')} frame=5m geometry={h.get('geometry')} direction={h.get('direction')} points={pv} ratios={ratios} PRZ=[{h.get('prz_low')},{h.get('prz_high')}] location={h.get('location')} strict_valid={h.get('strict_valid')} failed_rules={failed} targets={h.get('targets')}")
    except Exception as ex:
        print(f"[E V16.9 HARMONIC FORENSIC ERROR] {symbol} {str(ex)[:120]}")

def wave_map_15m(d15, entry_price=None):
    """15m AB=CD + Elliott impulse map. A validator/context engine, not an entry gate."""
    out={"abcd":{"valid":False},"elliott":{"valid":False},"targets":[],"source_frame":"15m"}
    try:
        x,piv=_compress_alternating_pivots(d15,3,180); av=max(float(atr(x,14)),float(x.c.iloc[-1])*.0015)
        # AB=CD: last L-H-L gives projected D; equality zone with practical Fibonacci extensions.
        if len(piv)>=3:
            for j in range(len(piv)-3,-1,-1):
                q=piv[j:j+3]
                if len(q)==3 and [z[2] for z in q]==['L','H','L']:
                    A,B,C=[z[1] for z in q]; ab=B-A
                    if ab>0 and C>A:
                        d_eq=C+ab; d127=C+1.272*ab; d1618=C+1.618*ab
                        out['abcd']={"valid":True,"A":A,"B":B,"C":C,"D":d_eq,"D127":d127,"D1618":d1618,"completion_zone":[d_eq-.25*av,d_eq+.25*av]}
                        break
        # Elliott bullish impulse: use last alternating L-H-L-H-L, enforce W2 not below origin and W4 not below W1 high.
        if len(piv)>=5:
            for j in range(len(piv)-5,-1,-1):
                q=piv[j:j+5]
                if [z[2] for z in q]==['L','H','L','H','L']:
                    p0,w1,w2,w3,w4=[z[1] for z in q]; m1=w1-p0; m3=w3-w2
                    if m1>0 and m3>0 and w2>p0 and w3>w1 and w4>w1:
                        # W3 cannot be shortest is only knowable after W5; use standard projection ranges.
                        t1=w1; t2=w3; t3=w4+max(m1,m3*.618); t4=w4+max(m1*1.618,m3)
                        out['elliott']={"valid":True,"wave0":p0,"wave1":w1,"wave2":w2,"wave3":w3,"wave4":w4,"wave5_projected":t3,"extension":t4,"invalidation_wave2":p0,"invalidation_wave4":w1}
                        break
        ts=[]
        e=out['elliott']; a=out['abcd']
        if e.get('valid'):ts=[e['wave1'],e['wave3'],e['wave5_projected'],e['extension']]
        elif a.get('valid'):
            base=float(entry_price or x.c.iloc[-1]); ts=[z for z in [a['B'],a['D'],a['D127'],a['D1618']] if z>base]
        out['targets']=sorted(dict.fromkeys(round(float(z),12) for z in ts if z and (entry_price is None or z>float(entry_price))))
        return out
    except Exception as ex:out['error']=str(ex)[:160];return out

def structural_no_chase_15m(d15, live_price, threshold_pct=STRUCTURAL_NO_CHASE_PCT):
    """Causal Structural anti-chase gate for NEW entries only.

    ALLOW before/at Wave-1 breakout and through +threshold_pct.
    BLOCK when price is > threshold_pct above Wave-1 high while Wave-3 is still
    extending and no confirmed Wave-4 reset exists.
    ALLOW again after a confirmed H-L sequence above Wave-1 (Wave-3 high -> Wave-4 low).
    Existing positions are never affected.
    """
    out={"block":False,"reason":"NO_VALID_012","threshold_pct":float(threshold_pct),
         "wave0":None,"wave1":None,"wave2":None,"wave3":None,"wave4":None,
         "breakout_pct":None,"wave4_reset_confirmed":False}
    try:
        x,piv=_compress_alternating_pivots(d15,3,220)
        px=float(live_price)
        # Latest causal bullish 0-1-2 sequence: L-H-L with W2 above W0.
        base=None; base_idx=None
        for j in range(len(piv)-3,-1,-1):
            q=piv[j:j+3]
            if len(q)==3 and [z[2] for z in q]==['L','H','L']:
                w0,w1,w2=map(lambda z:float(z[1]),q)
                if w1>w0 and w2>w0 and w2<w1:
                    base=(w0,w1,w2); base_idx=j+2; break
        if base is None:
            return out
        w0,w1,w2=base
        out.update({"wave0":w0,"wave1":w1,"wave2":w2,"reason":"BELOW_OR_EARLY_W1_EXTENSION"})
        if w1<=0:return out
        ext=(px/w1-1.0)*100.0
        out["breakout_pct"]=round(ext,4)

        # A later confirmed H-L above W1 is treated as Wave-3 high + Wave-4 reset.
        tail=piv[base_idx+1:] if base_idx is not None else []
        for k in range(len(tail)-1):
            h,l=tail[k],tail[k+1]
            if h[2]=='H' and l[2]=='L' and float(h[1])>w1 and float(l[1])>w1:
                out.update({"wave3":float(h[1]),"wave4":float(l[1]),
                            "wave4_reset_confirmed":True,"reason":"WAVE4_RESET_REENABLE"})
                return out

        if ext>float(threshold_pct):
            out["block"]=True
            out["reason"]="STRUCTURAL_NO_CHASE_GT_1_25_BEFORE_W4"
        return out
    except Exception as ex:
        out["reason"]="NO_CHASE_DIAGNOSTIC_ERROR"
        out["error"]=str(ex)[:120]
        return out


def classical_structure_15m(d15, live_price):
    """Classical-pattern context for structural breakout. Never opens a CLASSICAL path."""
    try:
        x=d15.tail(120).reset_index(drop=True); px=float(live_price); av=max(float(atr(x,14)),px*.0015); h=x.h.astype(float); l=x.l.astype(float); c=x.c.astype(float)
        recent=x.tail(40); hi=float(recent.h.max()); lo=float(recent.l.min()); width=hi-lo
        ph=_pivot_highs(x,2); pls=[]
        for i in range(2,len(x)-2):
            if float(l.iloc[i])<=float(l.iloc[i-2:i+3].min()):pls.append((i,float(l.iloc[i])))
        patterns=[]
        # Rectangle / horizontal base
        tol=max(.004*hi,.35*av); ht=sum(abs(float(z)-hi)<=tol for z in recent.h); lt=sum(abs(float(z)-lo)<=tol for z in recent.l)
        if ht>=2 and lt>=2 and width/max(px,1e-9)<=.12:patterns.append({"name":"RECTANGLE","breakout":hi,"score":78})
        # Ascending triangle: flat highs + rising lows.
        if len(pls)>=3 and ht>=2 and pls[-1][1]>pls[-2][1]>pls[-3][1]:patterns.append({"name":"ASCENDING_TRIANGLE","breakout":hi,"score":86})
        # Symmetrical triangle: descending highs + rising lows.
        if len(ph)>=3 and len(pls)>=3 and ph[-1][1]<ph[-2][1]<ph[-3][1] and pls[-1][1]>pls[-2][1]>pls[-3][1]:patterns.append({"name":"SYMMETRICAL_TRIANGLE","breakout":ph[-1][1],"score":82})
        # Bull flag: impulse followed by shallow, downward consolidation.
        if len(x)>=35:
            impulse=float(c.iloc[-20]/max(c.iloc[-35],1e-9)-1); pull=float(c.iloc[-1]/max(c.iloc[-20],1e-9)-1)
            if impulse>=.05 and -.05<=pull<=.01 and float(h.iloc[-10:].max())<float(h.iloc[-20:-10].max()):patterns.append({"name":"BULL_FLAG","breakout":float(h.iloc[-10:].max()),"score":80})
        best=max(patterns,key=lambda z:z['score']) if patterns else {"name":"NONE","breakout":None,"score":0}
        best['valid']=best['name']!='NONE';best['patterns']=patterns;best['source_frame']='15m';return best
    except Exception as ex:return {"valid":False,"name":"NONE","score":0,"error":str(ex)[:120],"source_frame":"15m"}

def momentum_source_15m(d15, regime=None):
    try:
        x=d15.tail(100); px=float(x.c.iloc[-1]); avgv=float(x.v.iloc[-30:-1].mean() or 1); rv=float(x.v.iloc[-1]/max(avgv,1e-12)); r=rsi(x.c); e9=ema(x.c,9);e21=ema(x.c,21)
        ret3=(px/float(x.c.iloc[-4])-1)*100; reasons=[]
        if rv>=1.5:reasons.append('VOLUME_EXPANSION')
        if px>float(e9.iloc[-1])>float(e21.iloc[-1]):reasons.append('TREND_ACCELERATION')
        if ret3>=1.0:reasons.append('PRICE_IMPULSE')
        if r>=60:reasons.append('MOMENTUM_RSI')
        if regime and float((regime or {}).get('btc15',0))<0 and ret3>0:reasons.append('RELATIVE_STRENGTH_VS_BTC')
        return {"score":min(100,20+min(30,max(0,(rv-1)*25))+min(25,max(0,ret3*8))+(15 if r>=60 else 0)+(10 if px>float(e9.iloc[-1])>float(e21.iloc[-1]) else 0)),"rvol15":round(rv,2),"rsi15":round(r,1),"ret45m_pct":round(ret3,2),"reasons":reasons}
    except Exception as ex:return {"score":0,"reasons":[],"error":str(ex)[:120]}

def execution_1m_confirm(symbol, level=None, route="HARMONIC"):
    """Route-specific execution on the latest CLOSED 1m candle.
    klines() already removes Binance's live candle, therefore iloc[-1] is closed.
    HARMONIC: bullish/reversal confirmation near/above PRZ.
    EXCEPTIONAL_COIN: continuation/hold confirmation; one tiny red candle alone is not a veto.
    MAJOR_STRUCTURAL_BREAKOUT: breakout/retest hold around governing level.
    """
    try:
        d=klines(symbol,'1m',80)
        if len(d)<3:
            return {"ok":False,"reason":"INSUFFICIENT_1M_BARS","bars":len(d),"route":route}
        b=d.iloc[-1]; prev=d.iloc[-2]
        o,h,l,c=map(float,(b.o,b.h,b.l,b.c)); pc=float(prev.c)
        body=abs(c-o); rng=max(h-l,1e-12); body_ratio=body/rng
        close_location=(c-l)/rng
        positive=c>o
        lvl=float(level or 0); threshold=(lvl*.9995) if lvl>0 else 0.0
        level_ok=True if lvl<=0 else c>=threshold
        micro_hold=bool(c>=pc*0.9995 and close_location>=0.35)
        bullish_reversal=bool(positive and (c>=pc or close_location>=0.60))
        breakout_hold=bool(level_ok and (positive or micro_hold))
        if route=="EXCEPTIONAL_COIN":
            ok=bool(positive or micro_hold)
            failed=[] if ok else ["EXCEPTIONAL_1M_MOMENTUM_HOLD_FAILED"]
        elif route=="MAJOR_STRUCTURAL_BREAKOUT":
            ok=breakout_hold
            failed=[]
            if not level_ok: failed.append("CLOSED_1M_BELOW_BREAKOUT_TOLERANCE")
            if level_ok and not (positive or micro_hold): failed.append("CLOSED_1M_BREAKOUT_HOLD_FAILED")
        else:
            # V16.6 Harmonic: the completed 5m model owns PRZ/model validity.
            # 1m is timing ONLY: enter on the first CLOSED green candle.
            # No extra momentum/body/close-location/PRZ re-test gate is allowed here.
            harmonic_momentum=bool(positive)
            ok=harmonic_momentum
            failed=[] if ok else ["WAIT_FIRST_CLOSED_1M_GREEN_CANDLE"]
        return {"ok":ok,"route":route,"positive":positive,"micro_hold":micro_hold,
                "bullish_reversal":bullish_reversal,"harmonic_momentum":locals().get("harmonic_momentum",False),"breakout_hold":breakout_hold,
                "open":o,"high":h,"low":l,"close":c,"prev_close":pc,
                "body_ratio":round(body_ratio,4),"close_location":round(close_location,4),
                "level":lvl,"threshold":threshold,"level_ok":level_ok,"closed_bar_index":-1,
                "failed_conditions":failed,
                "reason":f"{route}_CLOSED_1M_CONFIRM" if ok else ('+'.join(failed) or f"{route}_1M_WAIT")}
    except Exception as ex:
        return {"ok":False,"reason":"1M_EXEC_ERROR","route":route,"error":str(ex)[:100]}

def _wave_targets_for_entry(wave, entry, fallback_stop):
    """Return 15m model targets. Elliott: W1/W3/W5/extension; AB=CD: B/D/extensions."""
    ts=[float(z) for z in (wave or {}).get('targets',[]) if float(z)>entry*1.001]
    ru=max(entry-fallback_stop,entry*.002)
    while len(ts)<4:ts.append(entry+ru*(1.0+len(ts)*1.0))
    ts=sorted(ts)
    return ts[0],ts[1],ts[2],ts[3]

def _post_entry_15m_context(sym,p):
    try:
        d15=klines(sym,'15m',220); w=wave_map_15m(d15,float(p.get('entry',0))); return w
    except Exception:return {"abcd":{"valid":False},"elliott":{"valid":False},"targets":[]}

def _closed_model_bearish_reversal(sym, frame="15m"):
    try:
        d=klines(sym,frame,100); b=d.iloc[-1]; prev=d.iloc[-2]; o,h,l,c=map(float,(b.o,b.h,b.l,b.c)); po,pc=map(float,(prev.o,prev.c)); body=max(abs(c-o),1e-12);rng=max(h-l,1e-12);upper=max(0,h-max(o,c))
        engulf=c<o and pc>po and o>=pc and c<=po; star=c<o and upper>=2*body and body/rng<=.45; strong=c<o and body/rng>=.55
        return bool(engulf or star or strong),{"frame":frame,"bearish_engulf":engulf,"shooting_star":star,"strong_red":strong,"close":c}
    except Exception as ex:return False,{"frame":frame,"error":str(ex)[:100]}

def _closed_15m_bearish_reversal(sym):
    return _closed_model_bearish_reversal(sym,"15m")

# -----------------------------------------------------------------------------
# R10H — Harmonic Intelligence Assist (derived from B's open-formula PRZ logic)
# This is advisory by default. It never makes a Harmonic pattern mandatory for E.
# It uses CLOSED 5m candles only and supports bullish alignment + bearish conflict.
# -----------------------------------------------------------------------------
HARMONIC_SHADOW_ONLY = False  # V11: harmonic direction is a mandatory entry gate
HARMONIC_MIN_CONF = float(os.getenv("E_HARMONIC_MIN_CONF", "0.72"))
HARMONIC_STRONG_CONF = float(os.getenv("E_HARMONIC_STRONG_CONF", "0.80"))
HARMONIC_RETEST_ATR = float(os.getenv("E_HARMONIC_RETEST_ATR", "0.40"))
HARMONIC_BORDERLINE_TIMING_GAP = float(os.getenv("E_HARMONIC_BORDERLINE_TIMING_GAP", "2.0"))


def harmonic_assist(d5, live_price):
    empty={"name":"None","direction":"NONE","confidence":0.0,"prz_low":None,"prz_high":None,
           "stop":None,"targets":[],"location":"NONE","dist_prz_atr":999.0,"alignment_score":0.0,
           "long_alignment":False,"bearish_conflict":False,"ratios":{}}
    try:
        # Exclude the live/incomplete candle. B's strength is PRZ from confirmed structure.
        x=d5.iloc[:-1].tail(160).reset_index(drop=True)
        if len(x)<60: return empty
        w=2; piv=[]
        for i in range(w,len(x)-w):
            lo=float(x.l.iloc[i]); hi=float(x.h.iloc[i])
            if lo <= float(x.l.iloc[i-w:i+w+1].min()): piv.append((i,lo,'L'))
            if hi >= float(x.h.iloc[i-w:i+w+1].max()): piv.append((i,hi,'H'))
        piv.sort(key=lambda z:z[0])
        c=[]
        for q in piv:
            if c and c[-1][2]==q[2]:
                if (q[2]=='L' and q[1]<c[-1][1]) or (q[2]=='H' and q[1]>c[-1][1]): c[-1]=q
            else: c.append(q)
        if len(c)<5: return empty
        pts=c[-5:]; prices=[z[1] for z in pts]; types=[z[2] for z in pts]
        bullish=(types==['L','H','L','H','L']); bearish=(types==['H','L','H','L','H'])
        if not (bullish or bearish): return {**empty,"points":pts}
        X,A,B,C,D=prices
        if bullish:
            XA=A-X; AB=A-B; BC=C-B; CD=C-D; ad_num=A-D
        else:
            XA=X-A; AB=B-A; BC=B-C; CD=D-C; ad_num=D-A
        if min(XA,AB,BC,CD)<=1e-12: return {**empty,"points":pts}
        vals=[AB/XA,BC/AB,CD/BC,ad_num/XA]
        families=[
            ("Gartley",(.55,.70),(.382,.886),(1.13,1.75),(.72,.84)),
            ("Bat",(.35,.55),(.382,.886),(1.55,2.75),(.82,.93)),
            ("Butterfly",(.72,.84),(.382,.886),(1.55,2.75),(1.20,1.34)),
            ("Crab",(.35,.70),(.382,.886),(2.20,3.80),(1.50,1.72)),
            ("Deep Crab",(.82,.93),(.382,.886),(2.00,3.80),(1.50,1.72)),
            ("Cypher",(.35,.80),(.90,1.45),(1.20,2.40),(.70,.90)),
            ("Shark",(.35,.90),(.90,1.65),(1.13,2.80),(.82,1.18)),
            ("AB=CD",(.35,.90),(.382,.886),(.90,1.15),(.55,1.45)),
        ]
        best=None
        for fam in families:
            name=fam[0]; ranges=fam[1:]
            inside=sum(lo<=v<=hi for v,(lo,hi) in zip(vals,ranges))/4.0
            fits=[]
            for v,(lo,hi) in zip(vals,ranges):
                mid=(lo+hi)/2; half=max((hi-lo)/2,1e-9)
                fits.append(max(0.0,1.0-abs(v-mid)/(half*1.50)))
            conf=max(inside,sum(fits)/4.0)
            if best is None or conf>best[1]: best=(name,conf)
        name,conf=best
        av=max(float(atr(x,14)),1e-12)
        half=max(0.18*av,abs(C-D)*0.05); low=D-half; high=D+half
        px=float(live_price); location='BELOW_PRZ'; dist=999.0
        if low<=px<=high: location='IN_PRZ'; dist=0.0
        elif bullish and px>high: dist=(px-high)/av; location='RETEST' if dist<=HARMONIC_RETEST_ATR else 'ABOVE_PRZ'
        elif bullish: dist=(low-px)/av; location='BELOW_PRZ'
        elif bearish and px<low: dist=(low-px)/av; location='RETEST' if dist<=HARMONIC_RETEST_ATR else 'BELOW_PRZ'
        elif bearish: dist=(px-high)/av; location='ABOVE_PRZ'
        if bullish:
            stop=min(D,low)-0.35*av
            targets=[D+0.382*(C-D),D+0.618*(C-D),max(B,D+0.886*(C-D))]
        else:
            stop=max(D,high)+0.35*av
            targets=[D-0.382*(D-C),D-0.618*(D-C),min(B,D-0.886*(D-C))]
        long_align=bool(bullish and conf>=HARMONIC_MIN_CONF and location in ('IN_PRZ','RETEST'))
        bearish_conflict=bool(bearish and conf>=HARMONIC_MIN_CONF and location in ('IN_PRZ','RETEST'))
        align_score=(conf*100.0 if long_align else (-conf*100.0 if bearish_conflict else 0.0))
        return {"name":name,"direction":"BULLISH" if bullish else "BEARISH","confidence":round(conf,4),
                "prz_low":low,"prz_high":high,"stop":stop,"targets":targets,"location":location,
                "dist_prz_atr":round(dist,4),"alignment_score":round(align_score,2),
                "long_alignment":long_align,"bearish_conflict":bearish_conflict,"ratios":dict(zip(['AB_XA','BC_AB','CD_BC','AD_XA'],vals)),"points":pts}
    except Exception as ex:
        return {**empty,"error":str(ex)[:160]}


# === V13 B-MASTER DUAL-PATH PARITY ===
CLASSICAL_ENABLED = False  # Harmonic-only: Classical cannot qualify or open new positions.
CLASSICAL_MIN_SCORE = float(os.getenv("E_CLASSICAL_MIN_SCORE","75"))
CLASSICAL_RVOL_1M = float(os.getenv("E_CLASSICAL_RVOL_1M","1.25"))
CLASSICAL_MAX_CHASE_ATR = float(os.getenv("E_CLASSICAL_MAX_CHASE_ATR","0.85"))
CLASSICAL_RETEST_ENABLED = os.getenv("E_CLASSICAL_RETEST_ENABLED","1") == "1"
CLASSICAL_RETEST_LOOKBACK_1M = int(os.getenv("E_CLASSICAL_RETEST_LOOKBACK_1M","10"))
CLASSICAL_RETEST_TOL_ATR = float(os.getenv("E_CLASSICAL_RETEST_TOL_ATR","0.35"))
CLASSICAL_RETEST_MIN_RVOL = float(os.getenv("E_CLASSICAL_RETEST_MIN_RVOL","0.80"))
CLASSICAL_RETEST_MAX_CHASE_ATR = float(os.getenv("E_CLASSICAL_RETEST_MAX_CHASE_ATR","0.65"))

# V14.1 — Classical risk/profit policy approved by user.
# Classical and Harmonic remain independent entry paths (OR, never merged).
CLASSICAL_MIN_STOP_PCT = float(os.getenv("E_CLASSICAL_MIN_STOP_PCT","1.00"))
CLASSICAL_MAX_STOP_PCT = float(os.getenv("E_CLASSICAL_MAX_STOP_PCT","1.50"))
MIN_EXPECTED_PROFIT_USDT = float(os.getenv("E_MIN_EXPECTED_PROFIT_USDT","3.00"))

def _classical_strict_stop(entry, structural_stop):
    """Keep classical initial SL in a strict 1.0–1.5% band from entry.
    Structure still proposes the stop; this function prevents both noise-tight and oversized loss distance.
    """
    entry=float(entry); structural_stop=float(structural_stop)
    raw_pct=max(0.0,(entry-structural_stop)/max(entry,1e-12)*100.0)
    pct=max(CLASSICAL_MIN_STOP_PCT,min(CLASSICAL_MAX_STOP_PCT,raw_pct))
    return entry*(1.0-pct/100.0)

def _swing_points(df, w=3):
    x=df.iloc[:-1].reset_index(drop=True)
    pts=[]
    for i in range(w,len(x)-w):
        if float(x.l.iloc[i]) <= float(x.l.iloc[i-w:i+w+1].min()): pts.append((i,float(x.l.iloc[i]),"L"))
        if float(x.h.iloc[i]) >= float(x.h.iloc[i-w:i+w+1].max()): pts.append((i,float(x.h.iloc[i]),"H"))
    pts.sort(key=lambda z:z[0])
    out=[]
    for q in pts:
        if out and out[-1][2]==q[2]:
            if (q[2]=="L" and q[1]<out[-1][1]) or (q[2]=="H" and q[1]>out[-1][1]): out[-1]=q
        else: out.append(q)
    return out

def _classical_targets(entry, measured_target):
    move=max(float(measured_target)-float(entry),0.0)
    if move<=0:return []
    # Milestones are fractions of the model's measured move; TP4 is the full classical target.
    return [entry+0.500*move, entry+0.618*move, entry+0.786*move, entry+move]

def classical_long_assist(d15, live_price):
    """Detect bullish classical structures on E's governing 15m pattern frame."""
    empty={"valid":False,"name":"None","score":0.0,"breakout":None,"stop":None,"targets":[],
           "measured_target":None,"points":[],"reason":"NO_CLASSICAL_LONG"}
    try:
        x=d15.iloc[:-1].tail(180).reset_index(drop=True)
        if len(x)<70:return empty
        px=float(live_price); av=max(float(atr(x,14)),1e-12)
        pts=_swing_points(d15,3)
        lows=[q for q in pts if q[2]=="L"]; highs=[q for q in pts if q[2]=="H"]
        candidates=[]

        # Double Bottom: two comparable lows + intervening neckline.
        if len(lows)>=2:
            l1,l2=lows[-2],lows[-1]
            if l2[0]-l1[0]>=5 and abs(l2[1]/l1[1]-1)<=0.018:
                between=x.iloc[l1[0]:l2[0]+1]
                neck=float(between.h.max()); depth=max(neck-min(l1[1],l2[1]),0)
                if depth>0:
                    candidates.append(("DOUBLE_BOTTOM",neck,min(l1[1],l2[1])-0.30*av,neck+depth,92.0,[l1,l2]))

        # Inverse Head & Shoulders: L-H-L-H-L with head lowest, shoulders similar.
        if len(pts)>=5:
            for z in range(max(0,len(pts)-9),len(pts)-4):
                q=pts[z:z+5]
                if [a[2] for a in q]==["L","H","L","H","L"]:
                    ls,h1,head,h2,rs=q
                    shoulder_sim=abs(rs[1]/ls[1]-1)<=0.025
                    head_depth=min(ls[1],rs[1])-head[1]
                    if shoulder_sim and head_depth>=0.45*av:
                        neck=(h1[1]+h2[1])/2
                        candidates.append(("INVERSE_HEAD_SHOULDERS",neck,min(rs[1],head[1])-0.25*av,
                                           neck+(neck-head[1]),95.0,q))

        # Ascending Triangle: flat resistance + rising lows.
        if len(highs)>=2 and len(lows)>=2:
            h1,h2=highs[-2],highs[-1]; l1,l2=lows[-2],lows[-1]
            if abs(h2[1]/h1[1]-1)<=0.012 and l2[1]>l1[1]*1.003:
                resistance=max(h1[1],h2[1]); height=resistance-min(l1[1],l2[1])
                candidates.append(("ASCENDING_TRIANGLE",resistance,l2[1]-0.30*av,
                                   resistance+height,90.0,[h1,h2,l1,l2]))

        # Falling Wedge: falling highs + falling lows, but high slope steeper; bullish breakout.
        if len(highs)>=3 and len(lows)>=3:
            hs=highs[-3:]; ls=lows[-3:]
            dh=(hs[-1][1]-hs[0][1])/max(hs[-1][0]-hs[0][0],1)
            dl=(ls[-1][1]-ls[0][1])/max(ls[-1][0]-ls[0][0],1)
            if dh<0 and dl<0 and abs(dh)>abs(dl)*1.10:
                resistance=hs[-1][1]; height=max(h[1] for h in hs)-min(l[1] for l in ls)
                candidates.append(("FALLING_WEDGE",resistance,ls[-1][1]-0.30*av,
                                   resistance+height,91.0,hs+ls))

        # Bull Flag: strong pole followed by shallow/downward consolidation.
        pole_start=max(0,len(x)-55); cons_start=max(0,len(x)-18)
        pole_low=float(x.l.iloc[pole_start:cons_start].min()); pole_high=float(x.h.iloc[pole_start:cons_start].max())
        pole=(pole_high/pole_low-1) if pole_low>0 else 0
        cons=x.iloc[cons_start:]
        if pole>=0.035 and len(cons)>=10:
            ch=float(cons.h.max()); cl=float(cons.l.min())
            retr=(pole_high-cl)/max(pole_high-pole_low,1e-12)
            if retr<=0.55:
                candidates.append(("BULL_FLAG",ch,cl-0.25*av,ch+(pole_high-pole_low),89.0,[]))

        # Cup & Handle: rounded recovery near old high + small handle pullback.
        left=x.iloc[-120:-70] if len(x)>=120 else x.iloc[:25]
        cup=x.iloc[-90:-18]; handle=x.iloc[-18:]
        if len(left)>=10 and len(cup)>=30 and len(handle)>=10:
            rim=float(left.h.max()); bottom=float(cup.l.min()); handle_low=float(handle.l.min())
            depth=rim-bottom
            if depth>1.2*av and abs(float(cup.h.iloc[-8:].max())/rim-1)<=0.025 and handle_low>bottom+0.55*depth:
                candidates.append(("CUP_AND_HANDLE",rim,handle_low-0.25*av,rim+depth,93.0,[]))

        # Horizontal resistance breakout: captures historical-level explosions even without a named pattern.
        resistance=float(x.h.iloc[-65:-5].max())
        base_low=float(x.l.iloc[-30:].min())
        if resistance>base_low and (resistance/base_low-1)>=0.018:
            candidates.append(("MAJOR_RESISTANCE_BREAKOUT",resistance,base_low-0.25*av,
                               resistance+(resistance-base_low),86.0,[]))

        # Descending trendline breakout approximation from last three swing highs.
        if len(highs)>=3:
            hs=highs[-3:]
            if hs[0][1]>hs[1][1]>hs[2][1]:
                slope=(hs[-1][1]-hs[0][1])/max(hs[-1][0]-hs[0][0],1)
                projected=hs[-1][1]+slope*max((len(x)-1-hs[-1][0]),0)
                height=hs[0][1]-min(q[1] for q in lows[-3:]) if lows else 0
                if height>0:
                    candidates.append(("DESCENDING_TRENDLINE_BREAKOUT",projected,
                                       (lows[-1][1] if lows else px-2*av)-0.25*av,
                                       projected+height,88.0,hs))

        if not candidates:return empty
        # Prefer the strongest structure whose breakout is near current price.
        ranked=[]
        for name,bo,sl,tgt,base,pp in candidates:
            dist=(px-bo)/av
            proximity=max(0.0,12.0-abs(dist)*7.0)
            ranked.append((base+proximity,name,bo,sl,tgt,pp,dist))
        ranked.sort(reverse=True,key=lambda z:z[0])
        sc,name,bo,sl,tgt,pp,dist=ranked[0]
        targets=_classical_targets(px,tgt)
        return {"valid":bool(targets and sl<px),"name":name,"score":round(min(sc,100),1),
                "breakout":float(bo),"stop":float(sl),"targets":targets,"measured_target":float(tgt),
                "points":pp,"distance_breakout_atr":round(dist,3),"reason":"CLASSICAL_LONG_FOUND"}
    except Exception as ex:
        return {**empty,"error":str(ex)[:160]}

def classical_1m_trigger(symbol, classical):
    """
    V5.2 fast execution.
    Path A (unchanged): last CLOSED 1m candle confirms breakout + RVOL without chasing.
    Path B (new): if the breakout happened between scans, recover it only after a CLOSED 1m
    retest/reclaim of the breakout level. 3m remains supportive, never mandatory.
    """
    try:
        d1=klines(symbol,"1m",120); d3x=klines(symbol,"3m",90)
        if min(len(d1),len(d3x))<50:return {"ok":False,"reason":"FAST_DATA_SHORT"}

        closed=d1.iloc[:-1].copy()
        c=float(closed.c.iloc[-1]); o=float(closed.o.iloc[-1]); h=float(closed.h.iloc[-1]); l=float(closed.l.iloc[-1])
        prev_close=float(closed.c.iloc[-2]); bo=float(classical["breakout"])
        av=max(float(atr(closed,14)),1e-12)
        rv=float(closed.v.iloc[-1]/max(float(closed.v.iloc[-31:-1].mean()),1e-12))
        body=abs(c-o); rng=max(h-l,1e-12)
        clean_close=bool(c>bo and c>o and body/rng>=0.35)
        crossed=bool(prev_close<=bo*1.002 and c>bo)
        strong=bool(clean_close and rv>=CLASSICAL_RVOL_1M)
        chase=(c-bo)/av
        late=bool(chase>CLASSICAL_MAX_CHASE_ATR)

        c3=float(d3x.c.iloc[-2]); o3=float(d3x.o.iloc[-2])
        confirm3=bool(c3>o3 and c3>=bo)

        # V14.2 direct breakout: the breakout candle must already be CLOSED, then the NEXT
        # closed 1m candle must hold/continue above the level. A single price>breakout event is insufficient.
        b=closed.iloc[-2]; bp=closed.iloc[-3]
        b_o,b_h,b_l,b_c=map(float,(b.o,b.h,b.l,b.c)); bp_c=float(bp.c)
        b_rng=max(b_h-b_l,1e-12); b_body=abs(b_c-b_o)
        b_volbase=float(closed.v.iloc[-32:-2].mean())
        b_rv=float(b.v/max(b_volbase,1e-12))
        breakout_candle=bool(bp_c<=bo*1.002 and b_c>bo and b_c>b_o and b_body/b_rng>=0.30 and b_rv>=CLASSICAL_RVOL_1M)
        continuation_hold=bool(c>=bo and c>=b_c*0.998 and l>=bo-0.20*av and (c>o or c>=b_c))
        direct_ok=bool(breakout_candle and continuation_hold and rv>=CLASSICAL_RETEST_MIN_RVOL and not late)
        if direct_ok:
            return {"ok":True,"reason":"1M_BREAKOUT_NEXT_CANDLE_HOLD_CONFIRMED","entry_mode":"DIRECT_BREAKOUT",
                    "rvol_1m":round(rv,2),"breakout_rvol_1m":round(b_rv,2),"close_1m":c,"entry_price":c,"breakout":bo,
                    "chase_atr":round(chase,2),"confirm_3m":confirm3,"crossed_1m":True,
                    "retest_confirmed":False,"breakout_age_bars":1,"breakout_candle_close":b_c,
                    "confirmation_candle_close":c}

        # Smart retest recovery. Search recent CLOSED 1m bars for a real breakout that may have
        # occurred between scanner cycles, then demand a later reclaim near the breakout level.
        retest_ok=False; breakout_age=None; breakout_rvol=0.0; retest_rvol=rv
        if CLASSICAL_RETEST_ENABLED:
            look=max(3,min(CLASSICAL_RETEST_LOOKBACK_1M,len(closed)-35))
            start_i=max(31,len(closed)-look-1)
            end_i=len(closed)-1  # current closed candle is reserved for retest confirmation
            breakout_idx=None
            for i in range(start_i,end_i):
                ci=float(closed.c.iloc[i]); oi=float(closed.o.iloc[i]); hi=float(closed.h.iloc[i]); li=float(closed.l.iloc[i])
                pci=float(closed.c.iloc[i-1]); ri=max(hi-li,1e-12); bi=abs(ci-oi)
                volbase=float(closed.v.iloc[max(0,i-30):i].mean())
                rvi=float(closed.v.iloc[i]/max(volbase,1e-12))
                if pci<=bo*1.002 and ci>bo and ci>oi and bi/ri>=0.30 and rvi>=CLASSICAL_RVOL_1M:
                    breakout_idx=i; breakout_rvol=rvi

            if breakout_idx is not None and breakout_idx < len(closed)-1:
                breakout_age=(len(closed)-1)-breakout_idx
                # Current closed candle must revisit/hold the breakout zone and bullishly reclaim it.
                touched=bool(l <= bo + CLASSICAL_RETEST_TOL_ATR*av and h >= bo - CLASSICAL_RETEST_TOL_ATR*av)
                reclaimed=bool(c>=bo and c>o and body/rng>=0.20)
                not_broken=bool(l >= bo - CLASSICAL_RETEST_TOL_ATR*av)
                retest_volume_ok=bool(rv>=CLASSICAL_RETEST_MIN_RVOL or confirm3)
                retest_chase=(c-bo)/av
                retest_ok=bool(touched and reclaimed and not_broken and retest_volume_ok and retest_chase<=CLASSICAL_RETEST_MAX_CHASE_ATR)
                if retest_ok:
                    return {"ok":True,"reason":"1M_RETEST_RECLAIM_CONFIRMED","entry_mode":"SMART_RETEST",
                            "rvol_1m":round(rv,2),"breakout_rvol_1m":round(breakout_rvol,2),
                            "close_1m":c,"entry_price":c,"breakout":bo,"chase_atr":round(retest_chase,2),
                            "confirm_3m":confirm3,"crossed_1m":False,"retest_confirmed":True,
                            "breakout_age_bars":breakout_age}

        # Keep anti-chase. A late move is watched for retest rather than bought.
        reason="LATE_WAIT_RETEST" if late else "WAIT_1M_BREAKOUT_VOLUME"
        return {"ok":False,"reason":reason,"entry_mode":"WAIT",
                "rvol_1m":round(rv,2),"breakout_rvol_1m":round(breakout_rvol,2),
                "close_1m":c,"entry_price":c,"breakout":bo,"chase_atr":round(chase,2),
                "confirm_3m":confirm3,"crossed_1m":crossed,"retest_confirmed":False,
                "breakout_age_bars":breakout_age}
    except Exception as ex:
        return {"ok":False,"reason":"FAST_TRIGGER_ERROR","entry_mode":"ERROR","error":str(ex)[:120]}

def stochrsi_1m_state(symbol, limit=120):
    """Closed-1m StochRSI timing. TradingView-style RSI(14), Stoch(14), K=3, D=3."""
    try:
        d1=klines(symbol,"1m",limit)
        if len(d1)<45: return {"ok":False,"reason":"STOCHRSI_1M_DATA_SHORT"}
        c=d1.c.astype(float)
        delta=c.diff(); up=delta.clip(lower=0.0); dn=(-delta.clip(upper=0.0))
        au=up.ewm(alpha=1.0/STOCHRSI_RSI_LEN,adjust=False).mean()
        ad=dn.ewm(alpha=1.0/STOCHRSI_RSI_LEN,adjust=False).mean().replace(0,np.nan)
        rs=au/ad; r=100.0-(100.0/(1.0+rs))
        lo=r.rolling(STOCHRSI_STOCH_LEN).min(); hi=r.rolling(STOCHRSI_STOCH_LEN).max()
        raw=100.0*(r-lo)/(hi-lo).replace(0,np.nan)
        k=raw.rolling(STOCHRSI_K_SMOOTH).mean(); d=k.rolling(STOCHRSI_D_SMOOTH).mean()
        if pd.isna(k.iloc[-1]) or pd.isna(d.iloc[-1]): return {"ok":False,"reason":"STOCHRSI_1M_NOT_READY"}
        k0,k1=float(k.iloc[-2]),float(k.iloc[-1]); d0,d1v=float(d.iloc[-2]),float(d.iloc[-1])
        recent_min=float(pd.concat([k.tail(5),d.tail(5)]).min())
        bull_cross=bool(k0<=d0 and k1>d1v)
        bull_follow=bool(k1>d1v and k1>k0 and d1v>=d0)
        reset=bool(recent_min<=STOCHRSI_RESET_MAX)
        bear_cross=bool(k0>=d0 and k1<d1v)
        recent_max=float(pd.concat([k.tail(5),d.tail(5)]).max())
        overbought=bool(recent_max>=STOCHRSI_OVERBOUGHT)
        cur=d1.iloc[-1]; prev=d1.iloc[-2]
        positive=bool(float(cur.c)>float(cur.o) and float(cur.c)>=float(prev.c))
        negative=bool(float(cur.c)<float(cur.o) and float(cur.c)<=float(prev.c))
        return {"ok":True,"k":round(k1,2),"d":round(d1v,2),"k_prev":round(k0,2),"d_prev":round(d0,2),
                "reset":reset,"recent_min":round(recent_min,2),"bull_cross":bull_cross,"bull_follow":bull_follow,
                "overbought":overbought,"recent_max":round(recent_max,2),"bear_cross":bear_cross,
                "positive_candle":positive,"negative_candle":negative,"close":float(cur.c)}
    except Exception as ex:
        return {"ok":False,"reason":"STOCHRSI_1M_ERROR","error":str(ex)[:120]}

def harmonic_1m_confirmation(symbol, harmonic):
    """V14.5: completed 15m bullish Harmonic D/PRZ + closed 1m StochRSI bullish turn + positive candle; no redundant fast veto after model completion."""
    try:
        if not harmonic or harmonic.get("direction")!="BULLISH" or not harmonic.get("long_alignment"):
            return {"ok":False,"reason":"NO_COMPLETED_BULLISH_HARMONIC_PRZ"}
        d1=klines(symbol,"1m",100)
        if len(d1)<40:return {"ok":False,"reason":"HARMONIC_1M_DATA_SHORT"}
        st=stochrsi_1m_state(symbol,120)
        if not st.get("ok"):
            return {"ok":False,"reason":st.get("reason","WAIT_STOCHRSI_1M"),"stochrsi":st}
        prz_low=float(harmonic.get("prz_low") or 0); prz_high=float(harmonic.get("prz_high") or 0)
        recent=d1.tail(6)
        touched=bool(prz_low>0 and prz_high>0 and float(recent.l.min())<=prz_high*1.002 and float(recent.h.max())>=prz_low*0.998)
        stoch_turn=bool(st.get("reset") and (st.get("bull_cross") or st.get("bull_follow")))
        candle_ok=bool(st.get("positive_candle"))
        ok=bool(touched and stoch_turn and candle_ok)
        return {"ok":ok,"reason":"HARMONIC_STOCHRSI_1M_BULLISH_CONFIRM" if ok else "WAIT_HARMONIC_STOCHRSI_1M_CONFIRM",
                "prz_touched":touched,"stoch_turn":stoch_turn,"positive_candle":candle_ok,"stochrsi":st,
                "confirmation_close":st.get("close")}
    except Exception as ex:
        return {"ok":False,"reason":"HARMONIC_STOCHRSI_1M_CONFIRM_ERROR","error":str(ex)[:120]}

def classical_quality(setup, classical, fast):
    """100-point score: pattern 30, breakout 20, volume/momentum 15, structure 15, R:R 10, market/context 10."""
    pattern=min(30.0,float(classical.get("score",0))*0.30)
    breakout=20.0 if fast.get("crossed_1m") else (16.0 if fast.get("ok") else 8.0)
    volume=min(15.0,8.0+max(0.0,float(fast.get("rvol_1m",0))-1.0)*7.0)
    structure=min(15.0,float((setup.get("structure_state") or {}).get("confirm_score",0))*0.15)
    entry=float(setup["price"]); sl=float(classical["stop"]); t3=float(classical["targets"][2])
    rr=(t3-entry)/max(entry-sl,1e-12)
    rrpts=10.0 if rr>=2 else (8.0 if rr>=1.5 else (5.0 if rr>=1.1 else 0.0))
    mode=str((setup.get("regime") or {}).get("mode","YELLOW"))
    market=10.0 if mode=="GREEN" else (7.0 if mode=="YELLOW" else 4.0)
    return round(min(100.0,pattern+breakout+volume+structure+rrpts+market),1),rr

def classical_notional(quality):
    if quality>=93:return 700.0
    if quality>=85:return 500.0
    if quality>=75:return 300.0
    return 0.0


def evaluate(symbol, regime=None):
    """V3 FINAL: discover momentum, then wait for PAC/ribbon pullback + structural reclaim before execution."""
    regime=regime or {"mode":"YELLOW","points":3.0,"btc5":0.0,"btc15":0.0,"breadth":50.0}
    d3=klines(symbol,"3m",120); d5=klines(symbol,"5m",120); d15=klines(symbol,"15m",220); d1h=klines(symbol,"1h",220)
    if min(len(d3),len(d5),len(d15),len(d1h)) < 100: return None
    p=float(d5.c.iloc[-1]); p3=float(d3.c.iloc[-1])

    # --- Trend / momentum discovery ---
    e9=ema(d5.c,9); e21=ema(d5.c,21); e50=ema(d5.c,50)
    e21_15=ema(d15.c,21); e89_15=ema(d15.c,89); e200_15=ema(d15.c,200)
    e21_1h=ema(d1h.c,21); e89_1h=ema(d1h.c,89); e200_1h=ema(d1h.c,200)
    vol_ratio=float(d5.v.iloc[-3:].mean()/max(float(d5.v.iloc[-30:-3].mean()),1e-12))
    vol_expand=float(d5.v.iloc[-3:].mean()/max(float(d5.v.iloc[-12:-3].mean()),1e-12))
    ret5=float((p/d5.c.iloc[-4]-1)*100); ret15=float((d15.c.iloc[-1]/d15.c.iloc[-4]-1)*100)
    rv=rsi(d5.c)
    macd=ema(d5.c,12)-ema(d5.c,26); macd_sig=ema(macd,9); macd_pos=float(macd.iloc[-1]-macd_sig.iloc[-1])>0
    high20=float(d5.h.iloc[-21:-1].max()); high7=float(d5.h.iloc[-8:-1].max())
    breakout=p>high20; near_breakout=p>high7
    trend_5=p>float(e9.iloc[-1])>=float(e21.iloc[-1])
    trend_15=float(d15.c.iloc[-1])>float(e21_15.iloc[-1])
    trend_1h=float(d1h.c.iloc[-1])>float(e21_1h.iloc[-1])
    anchor_15=float(d15.c.iloc[-1])>float(e200_15.iloc[-1])
    anchor_1h=float(d1h.c.iloc[-1])>float(e200_1h.iloc[-1])
    a=atr(d5,14); atr_pct=(a/max(p,1e-12))*100
    est_daily_qv=float(d5.qv.iloc[-30:].mean()*288.0)

    # Advanced Market Intelligence for Hit & Run:
    # market regime + structure + liquidity sweep/reclaim + volume profile
    # + multi-horizon momentum + FVG + order block + VWAP.
    # This is weighted evidence, not a stack of hard indicator vetoes.
    try:
        ami = advanced_long_intelligence(
            {"3m": d3, "5m": d5, "15m": d15, "1h": d1h},
            weights={
                "regime":0.10,
                "structure":0.18,
                "liquidity":0.22,
                "volume_profile":0.14,
                "momentum":0.18,
                "fvg":0.05,
                "order_block":0.05,
                "vwap":0.08,
            },
        )
    except Exception as _amiex:
        ami = {"score":50.0, "components":{}, "reasons":[f"AMI unavailable: {_amiex}"],
               "positive_count":0, "strong_count":0, "negative_count":0}

    # Opportunity score 100: detect candidates without forcing entry.
    volume_pts=max(0.0,min(20.0,(vol_ratio-0.70)*12.0 + max(0.0,vol_expand-1.0)*5.0 + (3.0 if breakout and vol_ratio>=1.2 else 0.0)))
    momentum_pts=max(0.0,min(15.0,5.0+ret5*3.0+max(0.0,ret15)*0.8+(2.0 if macd_pos else 0.0)+(1.0 if 52<=rv<=78 else 0.0)))
    structure_pts=15.0 if breakout else (12.0 if near_breakout else (8.0 if p>float(e50.iloc[-1]) else 3.0))
    trend_pts=(3.0 if trend_5 else 1.0)+(2.5 if trend_15 else 0.0)+(2.5 if trend_1h else 0.0)+(1.0 if anchor_15 else 0.0)+(1.0 if anchor_1h else 0.0)
    vol_liq_pts=max(0.0,min(5.0,2.0*min(1.0,atr_pct/0.5)+3.0*min(1.0,est_daily_qv/max(MIN_QUOTE_VOLUME*6.0,1.0))))
    regime_pts=float(regime.get("points",3.0))
    raw70=volume_pts+momentum_pts+structure_pts+trend_pts+vol_liq_pts+regime_pts
    opportunity=max(0.0,min(100.0,raw70/70.0*100.0))
    opportunity = round(0.68*opportunity + 0.32*float(ami.get("score",50.0)), 1)

    # --- PAC + ribbon + confirmed pivot structure ---
    pacU15,pacL15,pacC15=pac(d15,10)
    pacU5,pacL5,pacC5=pac(d5,10)
    pacU3,pacL3,pacC3=pac(d3,10)
    ema5_15=ema(d15.c,5); ema12_15=ema(d15.c,12); ema36_15=ema(d15.c,36)
    ema5_3=ema(d3.c,5); ema12_3=ema(d3.c,12); ema36_3=ema(d3.c,36)
    st15=structure_state(d15); st3=structure_state(d3)

    # Pullback to 15m PAC / EMA5-12 or EMA12-36 ribbon, then resume.
    recent15=d15.iloc[-8:]
    zone_hi=max(float(pacU15.iloc[-1]), float(ema12_15.iloc[-1]), float(ema36_15.iloc[-1]))
    zone_lo=min(float(pacL15.iloc[-1]), float(ema5_15.iloc[-1]), float(ema12_15.iloc[-1]))
    pullback15=float(recent15.l.min()) <= zone_hi*1.004 and float(d15.c.iloc[-1]) >= float(pacC15.iloc[-1])
    resume15=float(d15.c.iloc[-1])>float(d15.o.iloc[-1]) and float(d15.c.iloc[-1])>float(pacU15.iloc[-1])

    # 3m execution trigger mirrors PAC exit/reclaim logic from the supplied tool, but only on closed candles.
    up3=(float(d3.c.iloc[-1])>float(d3.o.iloc[-1]) and float(d3.c.iloc[-1])>float(pacU3.iloc[-1]) and
         float(d3.c.iloc[-2])<=float(pacU3.iloc[-2]))
    up5=(float(d5.c.iloc[-1])>float(d5.o.iloc[-1]) and float(d5.c.iloc[-1])>float(pacU5.iloc[-1]) and
         float(d5.c.iloc[-2])<=float(pacU5.iloc[-2]))
    ribbon3=float(ema5_3.iloc[-1])>=float(ema12_3.iloc[-1])>=float(ema36_3.iloc[-1])
    higher_low3=bool(st3.get("hl")) or float(d3.l.iloc[-3:].min())>float(d3.l.iloc[-8:-3].min())

    # V4 reversal/confirmation engine: entry requires an actual event, not accumulated points.
    o1,h1,l1,c1 = map(float, [d3.o.iloc[-1],d3.h.iloc[-1],d3.l.iloc[-1],d3.c.iloc[-1]])
    op,hp,lp,cp = map(float, [d3.o.iloc[-2],d3.h.iloc[-2],d3.l.iloc[-2],d3.c.iloc[-2]])
    rng=max(h1-l1,1e-12); body=abs(c1-o1)
    lower_wick=min(o1,c1)-l1
    bullish_engulf=(c1>o1 and cp<op and c1>=op and o1<=cp)
    hammer=(c1>o1 and lower_wick>=body*1.5 and body/rng>=0.18 and c1>=l1+0.60*rng)
    strong_bull=(c1>o1 and body/rng>=0.55 and c1>=l1+0.75*rng)
    micro_break=c1>float(d3.h.iloc[-4:-1].max())
    reversal_candle=bullish_engulf or hammer or strong_bull
    volume_confirm=vol_ratio>=V4_MIN_RVOL and float(d3.v.iloc[-1])>=float(d3.v.iloc[-20:-1].mean())
    rsi_confirm=V4_MIN_RSI<=rv<=V4_MAX_RSI
    # VWAP + VP remain location confirmation, not hard filters.
    vwap=session_vwap(d5,48); vp=volume_profile(d5,72,24)
    vwap_dist=(p/vwap-1)*100 if vwap else 0.0
    poc_dist=(p/vp["poc"]-1)*100 if vp["poc"] else 0.0
    av=abs(vwap_dist)
    vwap_pts=14.0 if 0<=vwap_dist<=0.8 else (11.0 if av<=1.2 else (7.0 if av<=2.0 else (2.0 if av<=3.5 else 0.0)))
    in_value=vp["val"]<=p<=vp["vah"]
    near_poc=abs(p/vp["poc"]-1)*100<=0.8 if vp["poc"] else False
    above_vah=(p>vp["vah"] and (p/vp["vah"]-1)*100<=1.2) if vp["vah"] else False
    profile_pts=6.0 if near_poc else (5.0 if above_vah else (4.0 if in_value else (2.0 if abs(poc_dist)<=2.5 else 0.0)))

    location_confirm=(pullback15 or st15.get("hl") or higher_low3) and abs(vwap_dist)<=3.5

    # R9 adaptive confirmation: evidence is scored instead of requiring every indicator to be True.
    # A real price-action event is still required, but volume/RSI/location are confirmations, not brittle vetoes.
    trigger_event = bool(up3 or up5 or micro_break or bullish_engulf or hammer or strong_bull)
    confirm_score = 0.0
    confirm_score += 24.0 if (up3 or up5) else (16.0 if micro_break else 0.0)
    confirm_score += 18.0 if reversal_candle else 0.0
    confirm_score += 15.0 if higher_low3 else 0.0
    confirm_score += 14.0 if location_confirm else (7.0 if abs(vwap_dist)<=4.0 else 0.0)
    confirm_score += 14.0 if volume_confirm else (7.0 if vol_ratio>=MIN_ACTUAL_LIQUIDITY_RVOL else 0.0)
    confirm_score += 8.0 if rsi_confirm else (4.0 if 40<=rv<=86 else 0.0)
    confirm_score += 7.0 if ribbon3 else 0.0
    confirm_score = min(100.0, confirm_score)

    severe_illiquidity = vol_ratio < MIN_ACTUAL_LIQUIDITY_RVOL
    trigger_confirm = trigger_event and confirm_score >= MIN_CONFIRM_SCORE and not severe_illiquidity

    # Entry Timing 100 = PAC/ribbon 30 + structure 20 + location 20 + trigger 20 + anti-chase 10.
    pac_pts=(12.0 if pullback15 else 0.0)+(10.0 if resume15 else 0.0)+(8.0 if float(d15.c.iloc[-1])>float(pacC15.iloc[-1]) else 0.0)
    structure_timing=(10.0 if st15.get("hl") else 0.0)+(6.0 if st15.get("hh") else 0.0)+(4.0 if higher_low3 else 0.0)
    trigger_timing=(12.0 if up3 else (7.0 if up5 else 0.0))+(8.0 if ribbon3 else 0.0)
    location_timing=vwap_pts+profile_pts

    extension=(p/max(float(e21.iloc[-1]),1e-12)-1)*100
    if extension<=1.5 and rv<80: antichase_pts=10.0
    elif extension<=2.5 and rv<84: antichase_pts=7.0
    elif extension<=3.5 and rv<88: antichase_pts=3.0
    else: antichase_pts=0.0
    timing=max(0.0,min(100.0,pac_pts+structure_timing+location_timing+trigger_timing+antichase_pts))
    late_chase=extension>4.5 or vwap_dist>4.0 or rv>90

    # Candidate/confirm state for telemetry and future learning.
    if opportunity>=MIN_SCORE and timing>=MIN_ENTRY_TIMING and trigger_confirm and not late_chase: signal_state="BUY"
    elif opportunity>=MIN_SCORE and location_confirm: signal_state="ARMED"
    elif opportunity>=MIN_SCORE: signal_state="CANDIDATE"
    else: signal_state="DISCOVERED"

    # FIX1 structural stop: beyond the actual trigger/support with ATR breathing room.
    # Never tighten the stop merely to force a trade; position size absorbs the risk instead.
    pivot_low=st3.get("pivot_low") or st15.get("pivot_low")
    trigger_low=float(d3.l.iloc[-2:].min())
    micro_swing_low=float(d3.l.iloc[-6:].min())
    support_candidates=[x for x in [pivot_low,trigger_low,micro_swing_low] if x is not None and float(x)<p]
    nearest_support=max(map(float,support_candidates)) if support_candidates else float(d5.l.iloc[-6:].min())
    structural=nearest_support - 0.35*a
    atr_floor=p-2.0*a
    structural=min(structural, p*(1-MIN_STOP_PCT/100.0))
    structural=max(structural, p*(1-MAX_STOP_PCT/100.0), atr_floor)
    stop_pct=(p-structural)/p*100
    stop=max(0.0,structural)

    # V16.5: Harmonic is discovered/completed on CLOSED 5m. PRZ belongs to the 5m model.
    # 1m is execution timing only; Structural and Exceptional remain on their existing architecture.
    harmonic = harmonic_scan_15m(d5,p)
    harmonic["source_frame"] = "5m"
    _harmonic_forensic_line(symbol, harmonic)
    wave5 = wave_map_15m(d5,p)
    wave5["source_frame"] = "5m"
    wave15 = wave_map_15m(d15,p)
    classical_context15 = classical_structure_15m(d15,p)
    momentum15 = momentum_source_15m(d15,regime)

    # V15.2 CLEAN: Classical removed from new-entry logic.
    classical = {"valid":False,"name":"REMOVED","score":0.0}
    classical_fast = {"ok":False,"reason":"CLASSICAL_REMOVED_V15_2"}

    # V12 DUAL RANGE: completed 15m harmonic defines direction + SL/targets; 1m/3m/5m remain execution/timing only.
    try:
        d1=klines(symbol,"1m",90)
        e9_1=ema(d1.c,9); e9_3=ema(d3.c,9)
        one_bull=bool(float(d1.c.iloc[-2])>float(d1.o.iloc[-2]) and float(d1.c.iloc[-2])>=float(e9_1.iloc[-2]))
        three_bull=bool(float(d3.c.iloc[-2])>=float(e9_3.iloc[-2]))
        harmonic_fast=harmonic_1m_confirmation(symbol,harmonic)
        scalp_trigger=bool(harmonic_fast.get("ok",False))
    except Exception:
        one_bull=False; three_bull=False; harmonic_fast={"ok":False,"reason":"HARMONIC_FAST_FALLBACK_BLOCK"}; scalp_trigger=False

    structural_exception = exceptional_structural_assist(symbol,d1h,p,vol_ratio,ret5,ret15,regime,est_daily_qv,late_chase)
    try:
        # V15.2: HTF structure locates the level; one CLOSED positive 1m breakout confirms this path.
        # StochRSI is reserved for profit-exit timing, not entry.
        d1_exec=klines(symbol,"1m",90); cbar=d1_exec.iloc[-1]
        lvl=float(structural_exception.get("governing_level") or 0.0)
        c1=float(cbar.c); o1=float(cbar.o)
        one_min_break=bool(lvl>0 and c1>lvl*1.0005)
        structural_1m_ready=bool(one_min_break and c1>o1)
        structural_stoch={"ok":True,"reason":"ENTRY_STOCHRSI_NOT_REQUIRED_V15_2","close":c1,"positive_candle":c1>o1}
        structural_exception["one_min_break_confirmed"]=one_min_break
        structural_exception["one_min_close"]=c1
    except Exception:
        structural_stoch={"ok":False,"reason":"STRUCTURAL_STOCH_ERROR"}; structural_1m_ready=False

    return {"symbol":symbol,"price":p,"score":round(opportunity,2),"opportunity_score":round(opportunity,2),
            "entry_timing_score":round(timing,2),"signal_state":signal_state,
            "vol_ratio":vol_ratio,"rsi":rv,"ret5":ret5,"ret15":ret15,"breakout":breakout,"near_breakout":near_breakout,
            "vwap":vwap,"vwap_dist_pct":vwap_dist,"volume_profile":vp,"atr_pct":atr_pct,"est_daily_qv":est_daily_qv,
            "stop":stop,"stop_pct":stop_pct,"extension":extension,"late_chase":late_chase,"regime":regime,
            "harmonic_assist":harmonic,"wave_map_harmonic_5m":wave5,"wave_map_15m":wave15,"classical_context_15m":classical_context15,"momentum_source_15m":momentum15,"exceptional_coin":structural_exception,"structural_breakout":structural_exception,
            "structural_stochrsi_1m":structural_stoch,"structural_1m_ready":structural_1m_ready,
            "classical_assist":classical,"classical_fast_trigger":classical_fast,"harmonic_fast_trigger":harmonic_fast,"harmonic_scalp_trigger":scalp_trigger,"m1_bull":one_bull,"m3_bull":three_bull,
            "pac":{"u15":float(pacU15.iloc[-1]),"l15":float(pacL15.iloc[-1]),"c15":float(pacC15.iloc[-1]),
                   "u3":float(pacU3.iloc[-1]),"l3":float(pacL3.iloc[-1]),"c3":float(pacC3.iloc[-1])},
            "structure_state":{"m15":st15,"m3":st3,"pullback15":pullback15,"resume15":resume15,"up3":up3,"up5":up5,"ribbon3":ribbon3,
              "reversal_candle":reversal_candle,"bullish_engulf":bullish_engulf,"hammer":hammer,"strong_bull":strong_bull,
              "micro_break":micro_break,"volume_confirm":volume_confirm,"rsi_confirm":rsi_confirm,
              "location_confirm":location_confirm,"trigger_event":trigger_event,"confirm_score":round(confirm_score,2),"severe_illiquidity":severe_illiquidity,"trigger_confirm":trigger_confirm},
            "score_components":{"volume":round(volume_pts,2),"momentum":round(momentum_pts,2),"structure":round(structure_pts,2),
              "trend":round(trend_pts,2),"vol_liq":round(vol_liq_pts,2),"market_regime":round(regime_pts,2),"opportunity_raw70":round(raw70,2)},
            "timing_components":{"pac_ribbon":round(pac_pts,2),"pivot_structure":round(structure_timing,2),
              "vwap_volume_profile":round(location_timing,2),"pac_trigger":round(trigger_timing,2),"anti_chase":round(antichase_pts,2)}}

def target_dollars(score, timing=70, notional=500):
    # Compatibility helper. Live entries use smart_target(setup, notional).
    q=min(float(score),float(timing))
    base=max(10.0, V4_BASE_TARGET_USDT*(float(notional)/500.0))
    if q>=90: base*=1.25
    elif q<78: base*=0.80
    return round(min(V4_MAX_TARGET_USDT, base),2)

def desired_notional(score, timing=70):
    # Large size requires BOTH opportunity quality and entry quality.
    q=min(float(score),float(timing))
    if q>=97: return 5000.0
    if q>=95: return 3000.0
    if q>=90: return 2000.0
    if q>=85: return 1500.0
    if q>=80: return 1000.0
    if q>=75: return 700.0
    if q>=70: return 500.0
    return 300.0

def equity(s, prices=None):
    total=float(s.get("strategy_cash",0))
    for sym,p in s.get("positions",{}).items():
        px=(prices or {}).get(sym)
        if px is None:
            try: px=price(sym)
            except Exception: px=float(p["entry"])
        total += float(p["qty"])*float(px)
    return total

def open_risk(s):
    return sum(max(0,(float(p["entry"])-float(p["stop"]))*float(p["qty"])) for p in s.get("positions",{}).values())

def notional_audit(s, setup):
    eq=max(equity(s),1.0); cash=float(s["strategy_cash"])
    desired=desired_notional(setup["opportunity_score"],setup["entry_timing_score"])
    quality=min(float(setup["opportunity_score"]),float(setup["entry_timing_score"]))
    per_trade_risk_cap=min(eq*MAX_RISK_PER_TRADE_PCT/100, V4_BASE_RISK_USDT*(desired/500.0)*(1.15 if quality>=90 else 1.0))
    stop_pct=float(setup.get("stop_pct",0) or 0); risk_pct=max(stop_pct/100.0,1e-9)
    risk_based=per_trade_risk_cap/risk_pct
    raw=min(desired,risk_based,cash)
    operational_min=float(os.getenv("E_MIN_EXEC_NOTIONAL","50"))
    final=round(raw,2) if raw+1e-9>=operational_min else 0.0
    return {"equity":round(eq,4),"cash":round(cash,4),"quality":round(quality,2),"desired_target":round(desired,4),
            "risk_cap_usdt":round(per_trade_risk_cap,4),"stop_pct":round(stop_pct,4),
            "risk_based_notional":round(risk_based,4),"raw_notional":round(raw,4),
            "operational_min_notional":operational_min,"final_notional":final}

def choose_notional(s, setup):
    """Risk-first sizing: desired_notional is a TARGET, never a mandatory minimum."""
    eq=max(equity(s),1.0); cash=float(s["strategy_cash"])
    desired=desired_notional(setup["opportunity_score"],setup["entry_timing_score"])
    per_trade_risk_cap=min(eq*MAX_RISK_PER_TRADE_PCT/100, V4_BASE_RISK_USDT*(desired/500.0)*(1.15 if min(setup["opportunity_score"],setup["entry_timing_score"])>=90 else 1.0))
    risk_pct=max(float(setup["stop_pct"])/100.0,1e-9)
    risk_based=per_trade_risk_cap/risk_pct
    raw=min(desired,risk_based,cash)
    operational_min=float(os.getenv("E_MIN_EXEC_NOTIONAL","50"))
    return round(raw,2) if raw+1e-9>=operational_min else 0.0

def snapshot(s,force=False):
    global _last_snapshot
    if not AGENTIC_HUB_URL:return
    if not force and time.time()-_last_snapshot<AGENTIC_SNAPSHOT_SEC:return
    _last_snapshot=time.time()
    _hub("/snapshot",{"strategy":STRATEGY_CODE,"engine_id":ENGINE_ID,"cash":float(s["strategy_cash"]),
         "equity":equity(s),"realized_day":float(s.get("realized_day",0)),"realized_total":float(s.get("realized_total",0)),
         "positions":s.get("positions",{}),"payload":{"open_risk_usdt":open_risk(s),"no_daily_trade_cap":True,
         "no_profit_cap":True,"no_fixed_position_count_cap":True,"min_notional":MIN_NOTIONAL},"ts_uae":now_uae()})

def reset_day(s):
    today=datetime.now(UAE).date().isoformat()
    if s.get("realized_day_date")!=today:
        s["realized_day_date"]=today; s["realized_day"]=0.0

# === V11.5 TP3+ SMART EXIT — isolated management enhancement ===
# Entry logic, harmonic detection, sizing, SL, TP1/TP2 and capital rotation are unchanged.
TP3_1M_SMART_EXIT = os.getenv("E_TP3_1M_SMART_EXIT","true").lower() in ("1","true","yes","on")
TP4_EXTENSION_MULT = float(os.getenv("E_TP4_EXTENSION_MULT","0.618"))

def _tp4_extension(entry,tp2,tp3):
    """Synthetic extension milestone used only for monitoring/Telegram; never forces a sale."""
    base=max(tp3-tp2, tp3-entry, 0.0)
    return tp3 + TP4_EXTENSION_MULT*base if base>0 else tp3

# V14.2 — user-approved Dynamic Pre-TP1 Profit Shield. Milestones are protection only; never partial sells.
PRETP1_SHIELD_STAGES=((1.0,None),(2.0,0.0),(3.0,1.0),(5.0,3.0),(7.0,5.0),(10.0,7.0))

def _pretp1_shield_floor(entry, peak):
    mfe_pct=(float(peak)/max(float(entry),1e-12)-1.0)*100.0
    floor_pct=None; stage=0.0
    for activation,fp in PRETP1_SHIELD_STAGES:
        if mfe_pct+1e-9>=activation:
            stage=activation
            if fp is not None: floor_pct=fp
    floor=(float(entry)*(1.0+floor_pct/100.0)) if floor_pct is not None else 0.0
    return stage,floor_pct,floor,mfe_pct

def _setup_fingerprint_from_trade(p):
    path=str(p.get("entry_path","")).upper()
    if path=="HARMONIC":
        h=p.get("harmonic_assist") or {}; return f"H|{h.get('name')}|{float(h.get('prz_low') or 0):.12g}|{float(h.get('prz_high') or 0):.12g}"
    ex=p.get("exceptional_coin") or {}; lvl=float(p.get("entry_breakout",0) or ex.get("governing_level",0) or 0)
    return f"{path}|{lvl:.12g}" if path and lvl else None

def _setup_fingerprint_from_setup(setup):
    h=setup.get("harmonic_assist") or {}; ex=setup.get("exceptional_coin") or {}
    if h.get("long_alignment"):
        return f"H|{h.get('name')}|{float(h.get('prz_low') or 0):.12g}|{float(h.get('prz_high') or 0):.12g}"
    lvl=float(ex.get("governing_level") or 0)
    if ex.get("exceptional"): return f"EXCEPTIONAL|{lvl:.12g}"
    if ex.get("structural_signal"): return f"STRUCTURAL|{lvl:.12g}"
    return None

def _pre_tp1_thesis_failure(sym,p):
    """Confirmed 1m failed-breakout / pre-entry structural-low failure. No single-red-candle exit."""
    try:
        d1=klines(sym,"1m",90); closed=d1.iloc[:-1]
        if len(closed)<35:return False,"",{}
        c1=float(closed.c.iloc[-1]); c2=float(closed.c.iloc[-2])
        path=str(p.get("entry_path","HARMONIC")).upper()
        structural=float(p.get("entry_structural_low",0) or 0)
        if structural>0 and c1<structural and c2<structural:
            return True,"CONFIRMED_1M_STRUCTURAL_LOW_BREAK",{"c1":c1,"c2":c2,"structural_low":structural}
        return False,"",{}
    except Exception as ex:
        return False,"",{"error":str(ex)[:120]}

def _active_profit_floor(p):
    vals=[float(p.get("stop",0) or 0)]
    if p.get("tp1_hit"): vals.append(float(p.get("tp1",0) or 0))
    if p.get("tp2_hit"): vals.append(float(p.get("tp2",0) or 0))
    if p.get("tp3_milestone_notified"): vals.append(float(p.get("tp3",0) or 0))
    if p.get("tp4_milestone_notified"): vals.append(float(p.get("tp4_extension",0) or 0))
    if p.get("trend_rider_active"): vals.append(float(p.get("trend_rider_floor",0) or 0))
    vals.append(float(p.get("pretp1_profit_floor",0) or 0))
    return max(vals)

E_TREND_RIDER_ATR_MULT=float(os.getenv("E_TREND_RIDER_ATR_MULT","1.10"))
E_TREND_RIDER_MIN_PCT=float(os.getenv("E_TREND_RIDER_MIN_PCT","0.35"))
E_TREND_RIDER_MAX_PCT=float(os.getenv("E_TREND_RIDER_MAX_PCT","1.50"))
def _e_htf_trend_rider(symbol):
    try:
        m15=klines(symbol,"15m",140); h1=klines(symbol,"1h",140)
        e9=ema(m15.c,9); e21=ema(m15.c,21); e21h=ema(h1.c,21); e50h=ema(h1.c,50)
        healthy=bool(float(m15.c.iloc[-1])>=float(e9.iloc[-1])>=float(e21.iloc[-1]) and float(h1.c.iloc[-1])>=float(e21h.iloc[-1])>=float(e50h.iloc[-1]) and rsi(m15.c)>=50 and rsi(h1.c)>=47)
        av=max(float(atr(m15,14)),1e-12); px=float(m15.c.iloc[-1])
        trail=max(E_TREND_RIDER_MIN_PCT/100.0,min(E_TREND_RIDER_MAX_PCT/100.0,E_TREND_RIDER_ATR_MULT*av/max(px,1e-12)))
        return healthy,trail,{"rsi15m":round(rsi(m15.c),1),"rsi1h":round(rsi(h1.c),1)}
    except Exception as ex:
        return False,E_TREND_RIDER_MAX_PCT/100.0,{"error":str(ex)[:100]}

def _confirmed_1m_peak_reversal(sym):
    """
    Fast TP3+ exit trigger using CLOSED 1m candles only.
    Candle A must be a bearish peak-reversal pattern.
    Candle B must then confirm it. No intrabar decision and no single red-candle exit.
    """
    try:
        d1=klines(sym,"1m",90)
        if len(d1)<35:
            return False,{"reason":"INSUFFICIENT_1M_CANDLES"}

        # -1 is the still-forming candle; -3 = reversal candle A, -2 = closed confirmation B.
        rev=d1.iloc[-3]; conf=d1.iloc[-2]; pre=d1.iloc[-4]
        ro,rh,rl,rc=map(float,(rev.o,rev.h,rev.l,rev.c))
        co,ch,cl,cc=map(float,(conf.o,conf.h,conf.l,conf.c))
        po,pc=map(float,(pre.o,pre.c))

        rbody=max(abs(rc-ro),1e-12); rrng=max(rh-rl,1e-12)
        upper=max(0.0,rh-max(ro,rc))
        lower=max(0.0,min(ro,rc)-rl)

        bearish_engulf=bool(rc<ro and pc>po and ro>=pc and rc<=po)
        shooting_star=bool(upper>=2.0*rbody and upper>=2.0*max(lower,1e-12) and rbody/rrng<=0.45)
        bearish_rejection=bool(rc<ro and upper>=1.5*rbody and rc <= rl + 0.55*rrng)
        reversal_pattern=bool(bearish_engulf or shooting_star or bearish_rejection)

        # Confirmation must itself be closed and bearish, and prove follow-through.
        break_reversal_low=bool(cc < rl)
        close_below_mid=bool(cc < (ro+rc)/2.0 and cc < co)
        follow_through=bool(cc<co and (break_reversal_low or close_below_mid))

        # Peak quality: reversal candle should sit at/near the recent closed 1m high.
        recent_high=float(d1.h.iloc[-14:-3].max())
        near_peak=bool(rh >= recent_high*0.999)

        # Momentum rollover is supporting evidence, not a standalone trigger.
        rsi_now=float(rsi(d1.c.iloc[:-1]))
        rsi_prev=float(rsi(d1.c.iloc[:-2]))
        momentum_roll=bool(rsi_now < rsi_prev)

        confirmed=bool(reversal_pattern and follow_through and near_peak)
        evidence={
            "bearish_engulf":bearish_engulf,
            "shooting_star":shooting_star,
            "bearish_rejection":bearish_rejection,
            "break_reversal_low":break_reversal_low,
            "close_below_reversal_mid":close_below_mid,
            "near_recent_peak":near_peak,
            "momentum_roll":momentum_roll,
            "rsi":round(rsi_now,2),
            "reversal_high":rh,
            "reversal_low":rl,
            "confirmation_close":cc,
        }
        return confirmed,evidence
    except Exception as ex:
        return False,{"reason":"1M_REVERSAL_CHECK_ERROR","error":str(ex)[:120]}

def _closed_1m_bearish_reversal_candle(sym):
    try:
        d1=klines(sym,"1m",70); b=d1.iloc[-1]; prev=d1.iloc[-2]
        o,h,l,c=map(float,(b.o,b.h,b.l,b.c)); po,pc=map(float,(prev.o,prev.c))
        body=max(abs(c-o),1e-12); rng=max(h-l,1e-12); upper=max(0.0,h-max(o,c))
        engulf=bool(c<o and pc>po and o>=pc and c<=po); star=bool(c<o and upper>=2*body and body/rng<=0.45); strong_red=bool(c<o and body/rng>=0.55)
        return bool(engulf or star or strong_red),{"bearish_engulf":engulf,"shooting_star":star,"strong_red":strong_red,"close":c}
    except Exception as ex: return False,{"reason":"1M_REVERSAL_CANDLE_ERROR","error":str(ex)[:100]}

def _runner_trail_pct(sym):
    """Adaptive 3m volatility trail; management only, never an entry condition."""
    try:
        d3=klines(sym,"3m",60)
        a=max(atr(d3,14),1e-12)
        px=float(d3.c.iloc[-1])
        atr_pct=(a/max(px,1e-12))*100.0
        pct=atr_pct*RUNNER_TRAIL_ATR_MULT
        return max(RUNNER_TRAIL_MIN_PCT,min(RUNNER_TRAIL_MAX_PCT,pct))/100.0
    except Exception:
        return 0.0075

def _confirmed_bearish_reversal(sym):
    """Require closed-candle evidence on both 3m and 5m before a full safety exit."""
    try:
        d3=klines(sym,"3m",80); d5=klines(sym,"5m",100)
        if len(d3)<30 or len(d5)<30:
            return False,{"reason":"INSUFFICIENT_CANDLES"}
        def frame_signal(df):
            cur=df.iloc[-2]; prev=df.iloc[-3]
            o,h,l,c=map(float,(cur.o,cur.h,cur.l,cur.c))
            po,pc=map(float,(prev.o,prev.c))
            body=max(abs(c-o),1e-12); rng=max(h-l,1e-12)
            upper=max(0.0,h-max(o,c))
            engulf=bool(c<o and pc>po and o>=pc and c<=po)
            star=bool(c<o and upper>=2.0*body and body/rng<=0.45)
            e9=ema(df.c,9); e21=ema(df.c,21)
            trend=bool(c<float(e9.iloc[-2]) and float(e9.iloc[-2])<float(e21.iloc[-2]))
            rn=float(rsi(df.c.iloc[:-1])); rp=float(rsi(df.c.iloc[:-2]))
            fade=bool(rn<rp and rn<52)
            va=float(df.v.iloc[-22:-2].mean() or 0)
            volume=bool(va>0 and float(cur.v)>=va*1.05)
            pattern=bool(engulf or star)
            confirmed=bool((pattern and (trend or fade)) or (trend and fade and volume))
            return confirmed,{"bearish_engulf":engulf,"shooting_star":star,"trend_break":trend,
                              "momentum_fade":fade,"volume_confirm":volume,"rsi":round(rn,2)}
        c3,e3=frame_signal(d3); c5,e5=frame_signal(d5)
        return bool(c3 and c5),{"3m":e3,"5m":e5}
    except Exception as ex:
        return False,{"reason":"REVERSAL_CHECK_ERROR","error":str(ex)[:120]}

def close_position(s,sym,px,reason):
    p=s["positions"].pop(sym); proceeds=float(p["qty"])*px
    remaining_gross=proceeds-float(p["notional"])
    partial_pnl=float(p.get("partial_realized_pnl",0.0) or 0.0)
    gross_trade_pnl=partial_pnl+remaining_gross
    entry_fee=float(p.get("entry_fee_usdt",0) or 0); entry_slip=float(p.get("entry_slippage_usdt",0) or 0)
    exit_fee=proceeds*SPOT_FEE_RATE
    embedded_exit_slip=float(p.pop("_embedded_exit_slippage_usdt",0.0) or 0.0)
    # For stop exits, V17.2 already moved px adversely; record that cost but do not subtract it twice.
    if embedded_exit_slip>0:
        exit_slip=embedded_exit_slip; extra_exit_slip=0.0
    else:
        exit_slip=proceeds*max(0.0,VIRTUAL_EXECUTION_SLIPPAGE_BPS)/10000.0; extra_exit_slip=exit_slip
    net_trade_pnl=gross_trade_pnl-entry_fee-entry_slip-exit_fee-extra_exit_slip
    s["strategy_cash"]+=proceeds-exit_fee-extra_exit_slip
    s["realized_total"]+=net_trade_pnl; s["realized_day"]+=net_trade_pnl
    p.update({"gross_pnl":gross_trade_pnl,"entry_fee_usdt":entry_fee,"exit_fee_usdt":exit_fee,
              "total_fees_usdt":entry_fee+exit_fee,"entry_slippage_usdt":entry_slip,
              "exit_slippage_usdt":exit_slip,"total_slippage_usdt":entry_slip+exit_slip,"net_pnl":net_trade_pnl})
    rec={**p,"symbol":sym,"exit":px,"pnl":net_trade_pnl,"gross_pnl":gross_trade_pnl,"net_pnl":net_trade_pnl,
         "remaining_close_pnl":remaining_gross,"partial_realized_pnl":partial_pnl,"exit_reason":reason,"closed_at":now_uae()}
    s["closed"].append(rec); s["closed"]=s["closed"][-1000:]
    s["cooldown"][sym]=time.time()+COOLDOWN_MIN*60
    if net_trade_pnl<0 and str(p.get("entry_path","")).upper()=="CLASSICAL" and reason in ("CLASSICAL_SMART_STOP","CLASSICAL_THESIS_INVALIDATED","CONFIRMED_1M_FAILED_BREAKOUT","CONFIRMED_1M_STRUCTURAL_LOW_BREAK"):
        fp=_setup_fingerprint_from_trade(p)
        if fp: s.setdefault("failed_setups",{})[sym]={"fingerprint":fp,"failed_at":now_uae(),"reason":reason}
    save_state(s)
    emit("CLOSE",sym,p["trade_id"],p.get("score"),reason,{"entry":p["entry"],"exit":px,"gross_pnl":gross_trade_pnl,"net_pnl":net_trade_pnl,
         "entry_fee_usdt":entry_fee,"exit_fee_usdt":exit_fee,"entry_slippage_usdt":entry_slip,"exit_slippage_usdt":exit_slip,
         "total_fees_usdt":entry_fee+exit_fee,"total_slippage_usdt":entry_slip+exit_slip,"position_value":p.get("original_notional",p.get("notional",0)),"stop":p["stop"],"target_usdt":p["target_usdt"]})
    total_cost=entry_fee+exit_fee+entry_slip+exit_slip
    tg(f"{'🟢 PROFIT CLOSE' if net_trade_pnl>=0 else '🔴 LOSS CLOSE'} | E | HIT & RUN | COST-PARITY\n{_route_badge(p)}\n{sym}\nReason: {reason}\nGross PnL: {gross_trade_pnl:+.2f} USDT\nEntry Fee: -{entry_fee:.2f}\nExit Fee: -{exit_fee:.2f}\nEntry Slippage: -{entry_slip:.2f}\nExit Slippage: -{exit_slip:.2f}\nTotal Trading Cost: -{total_cost:.2f} USDT\nNET PnL: {net_trade_pnl:+.2f} USDT\nEntry {p['entry']:.8g} → Exit {px:.8g}\nCash: {s['strategy_cash']:.2f}")
    print(f"[E HIT & RUN CLOSE COST-PARITY] {sym} {reason} gross={gross_trade_pnl:+.2f} net={net_trade_pnl:+.2f}")


def manage(s):
    process_telegram_callbacks(s)
    dirty=False
    for sym in list(s.get("positions",{})):
        try: px=price(sym)
        except Exception: continue
        p=s["positions"].get(sym)
        if not p: continue
        entry=float(p["entry"]); qty=float(p["qty"])
        path=str(p.get("entry_path","HARMONIC")).upper()
        pnl_remaining=(px-entry)*qty

        peak=max(float(p.get("peak_price",entry)),px)
        if peak!=float(p.get("peak_price",entry)):
            p["peak_price"]=peak
            p["mfe_usdt"]=(peak-entry)*float(p.get("original_qty",qty))
            dirty=True

        # V17.1 Entry Protection — applies only to NEW V17.1 positions.
        # Existing positions from older engines are grandfathered and retain their
        # already-established stop/profit-management state.
        if (
            not p.get("tp1_hit")
            and str(p.get("engine_id_at_open", "")) in (
                "E-HITRUN-V17.1-ENTRY-PROTECTION-30PCT-3USDT",
                "E-HITRUN-V17.2-FAST-VIRTUAL-STOP-EXECUTION"
            )
        ):
            tp1_pre=float(p.get("tp1",0) or 0)
            original_qty=max(float(p.get("original_qty",qty) or qty),1e-12)

            # Before protection is armed, cap intended monetary loss at 3 USDT.
            # Never loosen an already-safer stop. Actual exit can differ slightly
            # because management acts on observed market prices, not an exchange order.
            money_stop=entry-(PRETP1_MAX_LOSS_USDT/original_qty)
            if not p.get("entry_protection_armed",False):
                safer_stop=max(float(p.get("stop",money_stop)),money_stop)
                if safer_stop>float(p.get("stop",0) or 0):
                    p["stop"]=safer_stop
                    dirty=True

            # Arm permanently once PEAK reaches 30% of Entry→TP1 distance.
            progress=0.0
            if tp1_pre>entry:
                progress=max(0.0,(peak-entry)/(tp1_pre-entry))

            if (
                not p.get("entry_protection_armed",False)
                and progress >= PRETP1_ENTRY_PROTECTION_TRIGGER
            ):
                p["entry_protection_armed"]=True
                p["entry_protection_armed_at"]=now_uae()
                p["stop"]=max(float(p.get("stop",0) or 0),entry)
                p.setdefault("profit_events",[]).append({
                    "ts":now_uae(),
                    "event":"PRETP1_ENTRY_PROTECTION_ARMED",
                    "trigger_pct":PRETP1_ENTRY_PROTECTION_TRIGGER*100.0,
                    "progress_pct":progress*100.0,
                    "entry":entry,
                    "peak":peak
                })
                emit(
                    "MILESTONE",sym,p["trade_id"],p.get("score"),
                    "PRETP1_ENTRY_PROTECTION_ARMED",
                    {
                        "trigger_pct":PRETP1_ENTRY_PROTECTION_TRIGGER*100.0,
                        "progress_pct":progress*100.0,
                        "entry":entry,
                        "peak":peak,
                        "stop":p["stop"]
                    }
                )
                dirty=True

            # After arming, Entry is the strict live protection level. Equality is
            # allowed; only a true break below Entry exits the full position.
            if p.get("entry_protection_armed",False):
                p["stop"]=max(float(p.get("stop",0) or 0),entry)
                entry_break_eps=max(entry*1e-8,1e-12)
                if px < entry-entry_break_eps:
                    emit(
                        "EXIT_SIGNAL",sym,p["trade_id"],p.get("score"),
                        "PRETP1_ENTRY_BREAK_EXIT",
                        {"price":px,"entry":entry,"peak":peak,"progress_pct":progress*100.0}
                    )
                    close_position(s,sym,px,"PRETP1_ENTRY_BREAK_EXIT")
                    continue

            # Keep the existing thesis-failure safety check active before TP1.
            failed,freason,fevidence=_pre_tp1_thesis_failure(sym,p)
            if failed:
                emit("EXIT_SIGNAL",sym,p["trade_id"],p.get("score"),freason,fevidence)
                close_position(s,sym,px,freason); continue

        tp1=float(p.get("tp1",0) or 0); tp2=float(p.get("tp2",0) or 0); tp3=float(p.get("tp3",0) or 0)
        if not p.get("tp4_extension"):
            p["tp4_extension"]=_tp4_extension(entry,tp2,tp3); dirty=True
        tp4=float(p.get("tp4_extension",tp3) or tp3)
        p.setdefault("trend_rider_active",False)
        p.setdefault("trend_rider_floor",0.0)
        p.setdefault("tp3plus_exit_mode","AUTO")

        if tp1>entry and px>=tp1 and not p.get("tp1_hit"):
            p["tp1_hit"]=True; p["stop"]=max(float(p["stop"]),tp1); dirty=True
            emit("MILESTONE",sym,p["trade_id"],p.get("score"),"TP1_REACHED_PROFIT_FLOOR_ACTIVE",{"price":px,"floor":tp1,"path":path})
            tg(_tg_target_dashboard(sym,p,px)+"\nTP1 reached ✅ | TP1 is now the mandatory profit floor.",reply_markup=_tg_controls(p,"AUTO"))

        if tp2>entry and px>=tp2 and not p.get("tp2_hit"):
            p["tp2_hit"]=True; p["stop"]=max(float(p["stop"]),tp2)
            p["runner_active"]=True; p["runner_high"]=px; p["runner_trail_pct"]=_runner_trail_pct(sym); dirty=True
            emit("MILESTONE",sym,p["trade_id"],p.get("score"),"TP2_REACHED_PROFIT_FLOOR_ACTIVE",{"price":px,"floor":tp2,"path":path})
            tg(_tg_target_dashboard(sym,p,px)+"\nTP2 reached ✅ | TP2 is now the mandatory profit floor.",reply_markup=_tg_controls(p,"AUTO"))

        if p.get("runner_active"):
            p["runner_high"]=max(float(p.get("runner_high",px)),px)
            if tp3>entry and px>=tp3 and not p.get("tp3_milestone_notified"):
                p["tp3_milestone_notified"]=True; p["stop"]=max(float(p["stop"]),tp3)
                emit("MILESTONE",sym,p["trade_id"],p.get("score"),"TP3_REACHED_PROFIT_FLOOR_ACTIVE",{"price":px,"floor":tp3,"path":path})
                tg(_tg_target_dashboard(sym,p,px)+"\nTP3 reached ✅ | TP3 is now the mandatory profit floor.",reply_markup=_tg_controls(p,"AUTO")); _tg_send_chart(sym,p)
            if tp4>tp3 and px>=tp4 and not p.get("tp4_milestone_notified"):
                p["tp4_milestone_notified"]=True; p["stop"]=max(float(p["stop"]),tp4)
                healthy,tr,evidence=_e_htf_trend_rider(sym)
                p["trend_rider_active"]=bool(healthy); p["trend_rider_floor"]=tp4
                p["trend_rider_high"]=px; p["trend_rider_trail_pct"]=tr; p["trend_rider_evidence"]=evidence
                emit("MILESTONE",sym,p["trade_id"],p.get("score"),"TP4_REACHED_TREND_RIDER_CHECK",{"price":px,"floor":tp4,"trend_rider":healthy,"path":path})
                tg(_tg_target_dashboard(sym,p,px)+("\nTP4 reached ✅ | Trend Rider ACTIVE 🚀" if healthy else "\nTP4 reached ✅ | TP4 remains the hard floor."),reply_markup=_tg_controls(p,"AUTO")); _tg_send_chart(sym,p)
            dirty=True

        eps=max(entry*1e-8,1e-12)
        if p.get("trend_rider_active"):
            healthy,tr,evidence=_e_htf_trend_rider(sym)
            p["trend_rider_high"]=max(float(p.get("trend_rider_high",px)),px)
            p["trend_rider_floor"]=max(tp4,float(p.get("trend_rider_floor",tp4)),float(p["trend_rider_high"])*(1-tr))
            p["stop"]=max(float(p["stop"]),float(p["trend_rider_floor"])); p["trend_rider_evidence"]=evidence; dirty=True
            if px<float(p["trend_rider_floor"])-eps:
                close_position(s,sym,px,"TREND_RIDER_FLOOR_EXIT"); continue
        elif p.get("tp4_milestone_notified") and px<tp4-eps:
            close_position(s,sym,px,"TP4_PROFIT_LOCK_FULL_EXIT"); continue

        if p.get("tp3_milestone_notified") and not p.get("tp4_milestone_notified") and px<tp3-eps:
            close_position(s,sym,px,"TP3_PROFIT_LOCK_FULL_EXIT"); continue
        if p.get("tp2_hit") and not p.get("tp3_milestone_notified") and px<tp2-eps:
            close_position(s,sym,px,"TP2_PROFIT_LOCK_FULL_EXIT"); continue
        if p.get("tp1_hit") and not p.get("tp2_hit") and px<tp1-eps:
            close_position(s,sym,px,"TP1_PROFIT_LOCK_FULL_EXIT"); continue

        if px<=float(p["stop"]):
            if p.get("runner_active"): reason="FULL_POSITION_TRAILING_EXIT"
            elif p.get("tp1_hit"): reason="PROTECTED_STOP_AFTER_TP1"
            else: reason="SMART_HARD_STOP"

            # V17.2: this engine is PURE VIRTUAL; model the active stop as if it
            # were already resting at the exchange.  Using the next polled price
            # as the fill incorrectly converts polling latency into artificial
            # slippage (the V17.1 forensic audit showed this clearly).
            active_stop=float(p["stop"])
            slip=max(0.0,VIRTUAL_STOP_SLIPPAGE_BPS)/10000.0
            virtual_fill=active_stop*(1.0-slip)
            emit("EXIT_SIGNAL",sym,p["trade_id"],p.get("score"),
                 "V17_2_VIRTUAL_STOP_FILL",
                 {"observed_price":px,"active_stop":active_stop,
                  "virtual_fill":virtual_fill,"slippage_bps":VIRTUAL_STOP_SLIPPAGE_BPS,
                  "close_reason":reason})
            p["_embedded_exit_slippage_usdt"] = max(0.0, (active_stop-virtual_fill)*float(p.get("qty",0) or 0))
            close_position(s,sym,virtual_fill,reason); continue

        try:
            df=klines(sym,"3m",60); dm=klines(sym,"15m",160)
            e9=ema(df.c,9); e21=ema(df.c,21); rv=rsi(df.c)
            lost_fast=bool(float(df.c.iloc[-1])<float(e9.iloc[-1])<float(e21.iloc[-1]))

            if path=="HARMONIC" and not p.get("tp1_hit"):
                dh5=klines(sym,"5m",220)
                hnow=harmonic_scan_15m(dh5,px)
                e9h=ema(dh5.c,9); e21h=ema(dh5.c,21); rvh=rsi(dh5.c)
                lost_h5=bool(float(dh5.c.iloc[-1])<float(e9h.iloc[-1])<float(e21h.iloc[-1]))
                bullish=bool(hnow.get("direction")=="BULLISH" and hnow.get("strict_valid") and float(hnow.get("confidence",0) or 0)>=HARMONIC_MIN_CONF)
                p["live_harmonic_confidence"]=float(hnow.get("confidence",0) or 0)
                p["can_still_profit"]=bool(bullish or not lost_h5); dirty=True
                if pnl_remaining<0 and (not bullish) and lost_h5 and rvh<42:
                    close_position(s,sym,px,"HARMONIC_5M_THESIS_INVALIDATED"); continue

            profit_pct=(px/entry-1.0)*100.0
            # V16.5 route-specific model management. Harmonic returns to CLOSED 5m;
            # Exceptional/Structural retain the existing CLOSED 15m management unchanged.
            model_tf="5m" if path=="HARMONIC" else "15m"
            dmodel=klines(sym,model_tf,220 if model_tf=="15m" else 240)
            wctx=wave_map_15m(dmodel,float(p.get("entry",0)))
            p["live_wave_map_5m" if path=="HARMONIC" else "live_wave_map_15m"]=wctx
            near_completion=False; completion="NONE"
            am=wctx.get("abcd",{}) or {}; em=wctx.get("elliott",{}) or {}
            avm=max(float(atr(dmodel,14)),entry*.0015)
            if am.get("valid") and abs(px-float(am.get("D",px)))<=0.50*avm: near_completion=True; completion="ABCD_D"
            if em.get("valid"):
                for lab,key in (("ELLIOTT_W3","wave3"),("ELLIOTT_W5","wave5_projected")):
                    v=float(em.get(key,0) or 0)
                    if v>0 and abs(px-v)<=0.50*avm: near_completion=True; completion=lab
            revm,revmev=_closed_model_bearish_reversal(sym,model_tf)
            if profit_pct>0 and near_completion and revm:
                reason=f"{model_tf.upper()}_MODEL_COMPLETION_PLUS_BEARISH_REVERSAL"
                emit("EXIT_SIGNAL",sym,p["trade_id"],p.get("score"),reason,{"price":px,"profit_pct":profit_pct,"completion":completion,"model_frame":model_tf,"wave":wctx,"reversal":revmev})
                close_position(s,sym,px,reason); continue
            if CONFIRMED_REVERSAL_EXIT and p.get("tp1_hit") and profit_pct>=REVERSAL_MIN_PROFIT_PCT:
                reversal,evidence=_confirmed_bearish_reversal(sym)
                if reversal:
                    healthy,_,hte=_e_htf_trend_rider(sym)
                    if p.get("tp2_hit") and healthy:
                        emit("HOLD",sym,p["trade_id"],p.get("score"),"FAST_REVERSAL_IGNORED_HTF_HEALTHY",{"price":px,"evidence":evidence,"htf":hte,"path":path})
                    else:
                        close_position(s,sym,px,"CONFIRMED_BEARISH_REVERSAL_FULL_EXIT"); continue
        except Exception:
            pass
    if dirty: save_state(s)

# === CAPITAL ROTATION / OPPORTUNITY UPGRADE ===
ROTATION_MIN_AGE_MIN = float(os.getenv("E_ROTATION_MIN_AGE_MIN", "6"))
ROTATION_HARMONIC_EDGE = float(os.getenv("E_ROTATION_HARMONIC_EDGE", "0.06"))
ROTATION_MAX_SMALL_PROFIT_FRAC = float(os.getenv("E_ROTATION_MAX_SMALL_PROFIT_FRAC", "0.20"))

def _age_minutes(opened_at):
    try:
        d=datetime.fromisoformat(str(opened_at).replace("Z","+00:00"))
        if d.tzinfo is None: d=d.replace(tzinfo=UAE)
        return max(0.0,(datetime.now(UAE)-d.astimezone(UAE)).total_seconds()/60.0)
    except Exception: return 0.0

def _position_future_edge(sym,p,px):
    """Return (can_still_profit, harmonic_confidence, momentum_healthy, pnl)."""
    entry=float(p.get("entry",0) or 0); qty=float(p.get("qty",0) or 0); target=float(p.get("target_usdt",0) or 0)
    pnl=(px-entry)*qty
    try:
        d3=klines(sym,"3m",60); d15=klines(sym,"15m",160)
        e9=ema(d3.c,9); e21=ema(d3.c,21); rv=rsi(d3.c)
        momentum=bool(float(d3.c.iloc[-1])>=float(e9.iloc[-1]) and float(e9.iloc[-1])>=float(e21.iloc[-1]) and rv>=48)
        h=harmonic_assist(d15,px); hc=float(h.get("confidence",0) or 0)
        harmonic_support=bool(h.get("direction")=="BULLISH" and hc>=HARMONIC_MIN_CONF)
        remaining=max(0.0,target-pnl) if target>0 else 0.0
        can_profit=bool(momentum and (harmonic_support or pnl>0) and (target<=0 or remaining>=target*0.20))
        return can_profit,hc,momentum,pnl
    except Exception:
        return bool(pnl>0),float((p.get("harmonic_assist") or {}).get("confidence",0) or 0),False,pnl

def maybe_rotate_capital(s, new_setup):
    nh=new_setup.get("harmonic_assist",{}) or {}
    if not bool(nh.get("long_alignment",False)):
        return False
    new_conf=float(nh.get("confidence",0) or 0)
    candidates=[]
    for sym,p in list(s.get("positions",{}).items()):
        try:
            px=price(sym); age=_age_minutes(p.get("opened_at")); target=float(p.get("target_usdt",0) or 0)
            if age < ROTATION_MIN_AGE_MIN: continue
            if float(p.get("pretp1_profit_floor",0) or 0)>0: continue
            can_profit,cur_conf,momentum,pnl=_position_future_edge(sym,p,px)
            # Core rule: never rotate a position that still has a credible path to profit.
            if can_profit: continue
            # Do not give away a meaningful existing profit merely to chase another setup.
            if target>0 and pnl>target*ROTATION_MAX_SMALL_PROFIT_FRAC: continue
            if new_conf < max(HARMONIC_MIN_CONF,cur_conf+ROTATION_HARMONIC_EDGE): continue
            candidates.append((cur_conf,age,pnl,sym,px,momentum))
        except Exception: continue
    if not candidates: return False
    cur_conf,age,pnl,sym,px,momentum=sorted(candidates,key=lambda x:(x[0],x[2],-x[1]))[0]
    print(f"[E V11 CAPITAL ROTATION] release={sym} old_harm={cur_conf:.2f} new={new_setup.get('symbol')}:{new_conf:.2f} age={age:.1f}m pnl={pnl:+.2f} can_still_profit=False")
    close_position(s,sym,px,"CAPITAL_ROTATION_HIGHER_HARMONIC_EDGE")
    return True

def audit_decision(setup, decision, reason):
    try:
        DECISION_AUDIT_PATH.parent.mkdir(parents=True,exist_ok=True)
        row={
            "ts_uae":now_uae(),"symbol":setup.get("symbol",""),"decision":decision,"reason":reason,
            "opportunity":setup.get("opportunity_score"),"timing":setup.get("entry_timing_score"),
            "confirm":(setup.get("structure_state") or {}).get("confirm_score"),
            "rvol":setup.get("vol_ratio"),"rsi":setup.get("rsi"),"vwap_dist":setup.get("vwap_dist_pct"),
            "regime":(setup.get("regime") or {}).get("mode"),"session":setup.get("session_uae",_session_name())
        }
        exists=DECISION_AUDIT_PATH.exists()
        with DECISION_AUDIT_PATH.open("a",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(row.keys()))
            if not exists: w.writeheader()
            w.writerow(row)
    except Exception as e:
        print("[DECISION AUDIT WARN]",str(e)[:120])


def audit_gate(setup, stage, passed, reason, extra=None):
    """Forensic BUY->OPEN trace. One row per gate so every rejected BUY has an exact blocker."""
    try:
        harm=setup.get("harmonic_assist",{}) or {}
        row={
            "ts_uae":now_uae(),"symbol":setup.get("symbol",""),"signal_state":setup.get("signal_state",""),
            "stage":stage,"passed":bool(passed),"reason":reason,
            "price":setup.get("price"),"stop":setup.get("stop"),
            "opportunity":setup.get("opportunity_score"),"timing":setup.get("entry_timing_score"),
            "confirm":(setup.get("structure_state") or {}).get("confirm_score"),
            "rvol":setup.get("vol_ratio"),"rsi":setup.get("rsi"),"vwap_dist":setup.get("vwap_dist_pct"),
            "regime":(setup.get("regime") or {}).get("mode"),"breadth":(setup.get("regime") or {}).get("breadth"),
            "btc5":(setup.get("regime") or {}).get("btc5"),"btc15":(setup.get("regime") or {}).get("btc15"),
            "session":setup.get("session_uae",_session_name()),
            "harmonic_pattern":harm.get("pattern"),"harmonic_direction":harm.get("direction"),
            "harmonic_confidence":harm.get("confidence"),"harmonic_location":harm.get("location"),
            "harmonic_long_alignment":harm.get("long_alignment"),"harmonic_bearish_conflict":harm.get("bearish_conflict")
        }
        for k,v in (extra or {}).items(): row[k]=v
        row=_json_safe(row)
        GATE_AUDIT_PATH.parent.mkdir(parents=True,exist_ok=True)
        exists=GATE_AUDIT_PATH.exists()
        with GATE_AUDIT_PATH.open("a",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(row.keys()),extrasaction="ignore")
            if not exists: w.writeheader()
            w.writerow(row)
    except Exception as e:
        print("[GATE AUDIT WARN]",str(e)[:120])

def _gate_fail(setup, stage, reason, decision="TRACK", extra=None):
    audit_gate(setup,stage,False,reason,extra)
    audit_decision(setup,decision,reason)
    emit(decision,setup.get("symbol",""),score=setup.get("opportunity_score"),reason=reason,payload={**setup,**(extra or {})})
    if str(setup.get("signal_state","")).upper()=="BUY":
        print(f"[E BUY->OPEN BLOCK] {setup.get('symbol')} stage={stage} reason={reason} opp={float(setup.get('opportunity_score',0) or 0):.1f} timing={float(setup.get('entry_timing_score',0) or 0):.1f}")

def validation_count(s):
    return len(s.get("closed",[]))

def write_validation_report(s):
    rows=list(s.get("closed",[]))[-VALIDATION_LIMIT:]
    if not rows: return
    pnls=[float(x.get("pnl",0) or 0) for x in rows]
    wins=[x for x in pnls if x>0]; losses=[x for x in pnls if x<0]
    gross_win=sum(wins); gross_loss=abs(sum(losses))
    reasons={}
    for x in rows:
        r=str(x.get("exit_reason","UNKNOWN")); reasons.setdefault(r,{"count":0,"pnl":0.0})
        reasons[r]["count"]+=1; reasons[r]["pnl"]+=float(x.get("pnl",0) or 0)
    report={
      "engine_id":ENGINE_ID,"trades":len(rows),"net_pnl":round(sum(pnls),4),
      "wins":len(wins),"losses":len(losses),"win_rate_pct":round(100*len(wins)/len(rows),2),
      "avg_win":round(gross_win/max(1,len(wins)),4),"avg_loss":round(-gross_loss/max(1,len(losses)),4),
      "profit_factor":round(gross_win/gross_loss,4) if gross_loss>0 else None,
      "ending_equity":round(equity(s),4),"exit_reasons":reasons,"generated_at":now_uae()}
    VALIDATION_REPORT_PATH.parent.mkdir(parents=True,exist_ok=True)
    VALIDATION_REPORT_PATH.write_text(json.dumps(report,indent=2,allow_nan=False))
    print("[E V11 HARMONIC SCALPER COMPLETE]",json.dumps(report,allow_nan=False))

def exceptional_opportunity_check(setup):
    """Strict evidence test. This is an exception path, never a broad market-filter relaxation."""
    regime=setup.get("regime",{}) or {}
    mode=str(regime.get("mode","YELLOW")).upper()
    btc5=float(regime.get("btc5",0.0) or 0.0)
    btc15=float(regime.get("btc15",0.0) or 0.0)
    breadth=float(regime.get("breadth",50.0) or 50.0)
    harm=setup.get("harmonic_assist",{}) or {}
    st=setup.get("structure_state",{}) or {}

    ret5=float(setup.get("ret5",0.0) or 0.0)
    ret15=float(setup.get("ret15",0.0) or 0.0)
    rs5=ret5-btc5
    rs15=ret15-btc15
    hconf=float(harm.get("confidence",0.0) or 0.0)
    opp=float(setup.get("opportunity_score",0.0) or 0.0)
    timing=float(setup.get("entry_timing_score",0.0) or 0.0)
    confirm=float(st.get("confirm_score",0.0) or 0.0)
    rvol=float(setup.get("vol_ratio",0.0) or 0.0)

    critical_red=bool(
        mode=="RED" and
        breadth < EOM_CRITICAL_BREADTH and
        btc5 <= EOM_CRITICAL_BTC5 and
        btc15 <= EOM_CRITICAL_BTC15
    )

    evidence={
        "enabled":EOM_ENABLED,
        "mode":mode,
        "critical_red":critical_red,
        "harmonic_conf":round(hconf,3),
        "opportunity":round(opp,2),
        "timing":round(timing,2),
        "confirm":round(confirm,2),
        "rvol":round(rvol,2),
        "ret5":round(ret5,3),
        "ret15":round(ret15,3),
        "btc5":round(btc5,3),
        "btc15":round(btc15,3),
        "rs5":round(rs5,3),
        "rs15":round(rs15,3),
        "breadth":round(breadth,1),
        "breakout":bool(setup.get("breakout")),
        "micro_break":bool(st.get("micro_break")),
        "higher_low":bool((st.get("m3") or {}).get("hl")) or bool(st.get("location_confirm")),
        "trigger_confirm":bool(st.get("trigger_confirm")),
        "harmonic_long":bool(harm.get("long_alignment")),
        "bearish_conflict":bool(harm.get("bearish_conflict")),
        "late_chase":bool(setup.get("late_chase")),
    }

    checks={
        "harmonic": evidence["harmonic_long"] and not evidence["bearish_conflict"] and hconf>=EOM_MIN_HARMONIC_CONF,
        "quality": opp>=EOM_MIN_OPPORTUNITY and timing>=EOM_MIN_TIMING and confirm>=EOM_MIN_CONFIRM,
        "volume": rvol>=EOM_MIN_RVOL,
        "relative_strength": rs5>=EOM_MIN_RS5 and rs15>=EOM_MIN_RS15,
        "structure": bool(evidence["breakout"] or evidence["micro_break"] or evidence["higher_low"]),
        "trigger": evidence["trigger_confirm"],
        "anti_chase": not evidence["late_chase"],
    }
    evidence["checks"]=checks

    if not EOM_ENABLED:
        return False,evidence,"EOM_DISABLED"
    if critical_red:
        return False,evidence,"CRITICAL_RED_ABSOLUTE_VETO"

    failed=[k for k,v in checks.items() if not v]
    if failed:
        return False,evidence,"EOM_FAIL_"+",".join(failed).upper()
    return True,evidence,"EOM_STRICT_PASS"



# === V11.9 PROFIT SELECTIVITY — isolated entry economics enhancement ===
# Filters technically valid trades whose projected full-position TP3 payoff is too small.
# All harmonic, stop, TP management, Profit-Lock, Telegram, EOM and capital rotation logic remains intact.
PROFIT_SELECTIVITY_ENABLED = os.getenv("E_PROFIT_SELECTIVITY_ENABLED","true").lower() in ("1","true","yes","on")
MIN_PROJECTED_TP3_USDT = float(os.getenv("E_MIN_PROJECTED_TP3_USDT","5.0"))
ELITE_MIN_PROJECTED_TP3_USDT = float(os.getenv("E_ELITE_MIN_PROJECTED_TP3_USDT","3.0"))
ELITE_HARMONIC_CONF = float(os.getenv("E_ELITE_HARMONIC_CONF","0.95"))
ELITE_MIN_QUALITY = float(os.getenv("E_ELITE_MIN_QUALITY","92"))

def projected_profit_gate(setup, harmonic_confidence, notional, entry, tp2, tp3):
    qty=float(notional)/max(float(entry),1e-12)
    tp2_usdt=max(0.0,(float(tp2)-float(entry))*qty)
    tp3_usdt=max(0.0,(float(tp3)-float(entry))*qty)
    tp3_pct=max(0.0,(float(tp3)/max(float(entry),1e-12)-1.0)*100.0)
    quality=min(float(setup.get("opportunity_score",0) or 0),
                float(setup.get("entry_timing_score",0) or 0))
    elite=bool(float(harmonic_confidence)>=ELITE_HARMONIC_CONF and quality>=ELITE_MIN_QUALITY)
    required=ELITE_MIN_PROJECTED_TP3_USDT if elite else MIN_PROJECTED_TP3_USDT
    evidence={"projected_tp2_usdt":round(tp2_usdt,4),
              "projected_tp3_usdt":round(tp3_usdt,4),
              "projected_tp3_pct":round(tp3_pct,4),
              "required_tp3_usdt":round(required,4),
              "elite":elite,
              "quality":round(quality,2),
              "notional":float(notional)}
    if not PROFIT_SELECTIVITY_ENABLED:
        return True,evidence,"PROFIT_SELECTIVITY_DISABLED"
    if tp3_usdt+1e-9 < required:
        return False,evidence,"PROJECTED_TP3_DOLLAR_PROFIT_TOO_SMALL"
    return True,evidence,"PROJECTED_PROFIT_PASS"

def _entry_diag_line(setup, path_checks, final, blocker, stage="ENTRY_PATH", extra=None):
    """One compact forensic line: discovery and execution are reported independently for all 3 OR paths."""
    sym=setup.get("symbol",""); ex=setup.get("exceptional_coin",{}) or {}; harm=setup.get("harmonic_assist",{}) or {}
    bits=[]
    for name in ("HARMONIC","EXCEPTIONAL_COIN","MAJOR_STRUCTURAL_BREAKOUT"):
        d=path_checks.get(name,{})
        bits.append(f"{name}=model:{'PASS' if d.get('model') else 'FAIL'},exec:{'PASS' if d.get('exec') else 'FAIL'}({d.get('exec_reason','NA')})")
    more=" ".join(f"{k}={v}" for k,v in (extra or {}).items())
    print(f"[E V16.5 ENTRY DIAG] {sym} signal={setup.get('signal_state')} regime={(setup.get('regime') or {}).get('mode')} opp={float(setup.get('opportunity_score',0) or 0):.1f} timing={float(setup.get('entry_timing_score',0) or 0):.1f} ecm={float(ex.get('score',0) or 0):.1f} structure={float(ex.get('structural_score',0) or 0):.1f} harm_conf={float(harm.get('confidence',0) or 0)*100:.1f} | {' | '.join(bits)} | FINAL={final} stage={stage} blocker={blocker} {more}".rstrip())


def try_open(s,setup):
    """V16.2 CLEAN: 15m discovers; closed 1m executes. Any ONE valid path can open. Every rejection names the exact blocker."""
    sym=setup["symbol"]
    path_checks={}
    def fail(stage,reason,decision="TRACK",extra=None):
        _entry_diag_line(setup,path_checks,"NO_ENTRY",reason,stage,extra)
        _gate_fail(setup,stage,reason,decision,extra)
        return False

    if sym in s["positions"]: return fail("PRECHECK","ALREADY_OPEN")
    if time.time()<float(s.get("cooldown",{}).get(sym,0)): return fail("PRECHECK","SYMBOL_COOLDOWN_ACTIVE")
    if _session_name()=="DEAD_00_04": return fail("SESSION","HARD_SESSION_BLOCK_00_04_UAE_NO_NEW_ENTRY")
    actual_rvol=float(setup.get("vol_ratio",0) or 0)
    if actual_rvol<MIN_ACTUAL_LIQUIDITY_RVOL:
        return fail("LIQUIDITY","ACTUAL_LIQUIDITY_TOO_LOW",extra={"actual_rvol":round(actual_rvol,4),"required_rvol":MIN_ACTUAL_LIQUIDITY_RVOL,"gap":round(MIN_ACTUAL_LIQUIDITY_RVOL-actual_rvol,4)})

    fp=_setup_fingerprint_from_setup(setup); failed=s.get("failed_setups",{}).get(sym) or {}
    if fp and failed.get("fingerprint")==fp: return fail("FRESH_SETUP","FAILED_SETUP_REUSE_BLOCKED",extra={"fingerprint":fp})

    harm=setup.get("harmonic_assist",{}) or {}; ex=setup.get("exceptional_coin",{}) or {}; entry=float(setup["price"])
    late=bool(setup.get("late_chase"))
    hlevel=float(harm.get("prz_high") or 0); slevel=float(ex.get("governing_level") or 0)
    exec_h=execution_1m_confirm(sym,None,"HARMONIC")
    exec_e=execution_1m_confirm(sym,None,"EXCEPTIONAL_COIN")
    exec_s=execution_1m_confirm(sym,slevel if slevel>0 else None,"MAJOR_STRUCTURAL_BREAKOUT")

    h_model=bool(harm.get("long_alignment",False) and not late)
    e_model=bool(ex.get("exceptional",False) and not late)
    s_model=bool(ex.get("structural_signal",False) and not late)
    path_checks={
        "HARMONIC":{"model":h_model,"exec":bool(exec_h.get("ok")),"exec_reason":exec_h.get("reason"),"level":hlevel,"close":exec_h.get("close"),"exec_audit":exec_h},
        "EXCEPTIONAL_COIN":{"model":e_model,"exec":bool(exec_e.get("ok")),"exec_reason":exec_e.get("reason"),"level":0.0,"close":exec_e.get("close"),"exec_audit":exec_e},
        "MAJOR_STRUCTURAL_BREAKOUT":{"model":s_model,"exec":bool(exec_s.get("ok")),"exec_reason":exec_s.get("reason"),"level":slevel,"close":exec_s.get("close"),"exec_audit":exec_s},
    }
    ready=[name for name,d in path_checks.items() if d["model"] and d["exec"]]
    if not ready:
        model_paths=[name for name,d in path_checks.items() if d["model"]]
        if not model_paths: reason="NO_VALID_MODEL_PATH"
        else:
            waits=[name for name in model_paths if not path_checks[name]["exec"]]
            reason="1M_EXECUTION_NOT_CONFIRMED:"+",".join(waits) if waits else "NO_VALID_EXECUTION_PATH"
        return fail("ENTRY_PATH",reason,extra={"path_checks":path_checks,"late_chase":late,"closed_1m_rule":"klines removes live bar; iloc[-1] is latest closed candle"})

    # deterministic priority only when multiple independent paths pass simultaneously.
    path=next(x for x in ("HARMONIC","EXCEPTIONAL_COIN","MAJOR_STRUCTURAL_BREAKOUT") if x in ready)
    wave15=setup.get("wave_map_15m",{}) or {}
    wave5=setup.get("wave_map_harmonic_5m",{}) or {}
    if path=="HARMONIC":
        stop=float(harm.get("stop") or 0)
        if stop<=0 or stop>=entry: return fail("RISK","INVALID_HARMONIC_STOP","RISK_SKIP",{"path":path,"stop":stop})
        # V16.6: initial Harmonic TP1-TP4 come ONLY from the completed 5m CD Fibonacci ladder.
        # AB=CD / Elliott remain post-entry 5m management context; they do not replace CD targets.
        hs=sorted({float(x) for x in (harm.get("targets") or []) if float(x)>entry*1.001})
        # Need four still-forward CD targets. If two or more Fibonacci stations are already behind
        # the entry, treat it as late/chasing rather than inventing generic R-multiple targets.
        if len(hs)<4: return fail("TARGETS","LATE_HARMONIC_ENTRY_INSUFFICIENT_FORWARD_CD_FIB_TARGETS","RISK_SKIP",{"path":path,"forward_cd_fib_targets":len(hs),"required":4,"all_cd_fib_targets":harm.get("targets") or [],"entry":entry})
        tp1,tp2,tp3,tp4=hs[:4]
        model_name=harm.get("name","HARMONIC"); confidence=float(harm.get("confidence",0) or 0)
    else:
        lvl=float(ex.get("governing_level") or 0); d15x=klines(sym,"15m",160); avx=max(float(atr(d15x,14)),entry*0.002)
        if path=="MAJOR_STRUCTURAL_BREAKOUT":
            if lvl<=0 or lvl>=entry*1.005: return fail("RISK","INVALID_STRUCTURAL_BREAKOUT_LEVEL","RISK_SKIP",{"path":path,"level":lvl,"entry":entry})
            # V17.0: user-approved Structural no-chase rule. This is an ENTRY gate only.
            # It does not change SL/TP/management and automatically re-enables after a confirmed Wave-4 reset.
            no_chase=structural_no_chase_15m(d15x,entry)
            setup["structural_no_chase"]=_json_safe(no_chase)
            if bool(no_chase.get("block")):
                return fail("STRUCTURAL_NO_CHASE",str(no_chase.get("reason")),"TRACK",
                            {"path":path,"wave1":no_chase.get("wave1"),
                             "breakout_pct":no_chase.get("breakout_pct"),
                             "threshold_pct":no_chase.get("threshold_pct"),
                             "wave4_reset_confirmed":no_chase.get("wave4_reset_confirmed")})
            stop=max(lvl-0.65*avx,entry*(1-MAX_STOP_PCT/100)); stop=min(stop,entry*(1-MIN_STOP_PCT/100))
        else:
            stop=float(setup.get("stop") or 0)
            if stop<=0 or stop>=entry: stop=entry-max(1.5*avx,entry*MIN_STOP_PCT/100)
        if entry-stop<=0: return fail("RISK","INVALID_STOP","RISK_SKIP",{"path":path,"stop":stop})
        tp1,tp2,tp3,tp4=_wave_targets_for_entry(wave15,entry,stop)
        model_name=(wave15.get("elliott",{}).get("valid") and "ELLIOTT_15M") or (wave15.get("abcd",{}).get("valid") and "ABCD_15M") or path
        confidence=min(1.0,max(float(ex.get("score",0)),float(ex.get("structural_score",0)))/100)

    setup["stop"]=stop; setup["stop_pct"]=(entry-stop)/entry*100
    notional=choose_notional(s,setup)
    if notional<=0: return fail("CAPITAL_RISK","CASH_OR_RISK_BELOW_MINIMUM","RISK_SKIP",{"path":path,**notional_audit(s,setup)})
    qty=notional/entry; governing_target=tp3 if path=="HARMONIC" else tp4; expected=(governing_target-entry)*qty
    if expected<MIN_EXPECTED_PROFIT_USDT: return fail("ECONOMY","EXPECTED_PROFIT_BELOW_MINIMUM","ECONOMIC_SKIP",{"path":path,"expected_profit_usdt":round(expected,4),"minimum":MIN_EXPECTED_PROFIT_USDT})
    risk=(entry-stop)*qty; r1=(tp1-entry)*qty/max(risk,1e-9); r2=(tp2-entry)*qty/max(risk,1e-9); r3=(tp3-entry)*qty/max(risk,1e-9)
    trade_id=f"EV166-{int(time.time()*1000)}-{sym}"
    entry_fee_usdt, entry_slippage_usdt = _e_cost(notional)
    p={"trade_id":trade_id,"entry":entry,"qty":qty,"original_qty":qty,"notional":notional,"original_notional":notional,
       "spot_fee_rate":SPOT_FEE_RATE,"virtual_execution_slippage_bps":VIRTUAL_EXECUTION_SLIPPAGE_BPS,
       "entry_fee_usdt":entry_fee_usdt,"entry_slippage_usdt":entry_slippage_usdt,"exit_fee_usdt":0.0,"exit_slippage_usdt":0.0,
       "total_fees_usdt":entry_fee_usdt,"total_slippage_usdt":entry_slippage_usdt,"gross_pnl":0.0,"net_pnl":0.0,"stop":stop,"target_usdt":expected,"target_price":governing_target,"score":round(confidence*100,1),"opportunity_score":float(setup.get("opportunity_score",0)),"entry_timing_score":float(setup.get("entry_timing_score",0)),"rr_at_entry":r3,"market_regime":setup.get("regime",{}).get("mode"),"opened_at":now_uae(),"vol_ratio":setup.get("vol_ratio"),"rsi":setup.get("rsi"),"vwap":setup.get("vwap"),"volume_profile":_json_safe(setup.get("volume_profile",{})),"harmonic_assist":_json_safe(harm),"wave_map_harmonic_5m":_json_safe(wave5),"wave_map_15m":_json_safe(wave15),"classical_context_15m":_json_safe(setup.get("classical_context_15m",{})),"momentum_source_15m":_json_safe(setup.get("momentum_source_15m",{})),"entry_path":path,"model_name":model_name,"model_frame":("5m" if path=="HARMONIC" else "15m"),"execution_frame":"1m","management_frame":("5m" if path=="HARMONIC" else "15m"),"engine_id_at_open":ENGINE_ID,"target_model":{"reason":f"{path}_TARGETS","tp1":tp1,"tp2":tp2,"tp3":tp3,"tp4":tp4},"initial_stop":stop,"peak_price":entry,"mfe_usdt":0.0,"tp1":tp1,"tp2":tp2,"tp3":tp3,"tp4_extension":tp4,"tp1_hit":False,"tp2_hit":False,"runner_active":False,"tp3_milestone_notified":False,"tp4_milestone_notified":False,"tp3plus_exit_mode":"AUTO","partial_realized_pnl":0.0,"partial_realized_proceeds":0.0,"profit_events":[],"rr1_at_entry":r1,"rr2_at_entry":r2,"rr3_at_entry":r3,"can_still_profit":True,"entry_breakout":float(ex.get("governing_level") or 0) if path=="MAJOR_STRUCTURAL_BREAKOUT" else 0.0,"structural_no_chase":_json_safe(setup.get("structural_no_chase",{})),"exceptional_coin":_json_safe(ex) if path!="HARMONIC" else {},"pretp1_shield_stage":0.0,"pretp1_profit_floor":0.0,"pretp1_mfe_pct":0.0,"entry_protection_armed":False,"entry_protection_armed_at":None}
    _entry_diag_line(setup,path_checks,"OPEN","PASS","OPEN",{"selected_path":path,"notional":round(notional,2),"expected_profit":round(expected,2)})
    audit_gate(setup,"OPEN",True,"V16_6_ROUTE_SPECIFIC_OPEN",extra={"path":path,"model":model_name,"notional":notional,"path_checks":path_checks})
    audit_decision(setup,"OPEN",f"V16_6_{path}_ENTRY")
    s["strategy_cash"]-=notional+entry_fee_usdt+entry_slippage_usdt; s["positions"][sym]=p; save_state(s)
    emit("OPEN",sym,trade_id,round(confidence*100,1),f"V16_3_{path}_ENTRY",{**p,"position_value":notional,"risk_usdt":risk,"strategy_cash":s["strategy_cash"]})
    threading.Thread(target=send_entry_recommendation_chart,args=(sym,p,setup,risk,r3),daemon=True).start()
    print(f"[E V16.9 OPEN] {sym} path={path} entry={entry:.8g} stop={stop:.8g} size={notional:.2f}")
    return True

def main():
    s=load_state(); reset_day(s); save_state(s)
    print("[E STATE] E state namespace active; existing E positions/state are preserved and managed.")
    print("[E HIT & RUN V16.9] SPOT LONG ONLY | 15m MODEL ENGINE | ONE PATH: HARMONIC OR EXCEPTIONAL_COIN OR MAJOR_STRUCTURAL_BREAKOUT")
    print("[E V16.9 ENTRY] Harmonic=STRICT 5m XABCD/PRZ -> first closed green 1m -> 5m management | Exceptional/Structural unchanged")
    print("[E V16.9 SCANNERS] Harmonic strict 5m: Gartley/Bat/Butterfly/Crab/Deep Crab + dedicated Cypher XC + dedicated Shark OXABC | ALL defining rules mandatory | no 3-of-4 rescue")
    print("[E V16.8 FORENSIC] model discovery and closed-1m execution are separated for ALL three OR paths | exact blocker logged")
    print("[E V14 CHART] Telegram entry chart=5m/15m | model + breakout + ENTRY price + SL + TP1-TP4 + target economics")
    print("[AGENTIC LINK] E | hub="+(AGENTIC_HUB_URL or "OFF"))
    s["engine_id"]=ENGINE_ID; save_state(s)
    print(f"[E | HIT & RUN BUILD] {ENGINE_ID}")
    print("[E V16.8 ARCHITECTURE] HARMONIC 5m MODEL/PRZ -> 1m FAST ENTRY -> 5m MANAGEMENT | EXCEPTIONAL/STRUCTURAL unchanged | TP milestones are not ceilings")
    print(f"[E V15.2 TELEGRAM POLICY] TP profit floors | controls=CONTINUE/SELL/AUTO/STATUS/CHART | callbacks={TG_CALLBACKS_ENABLED} | no partial sale")
    print(f"[E | HIT & RUN RISK] mandatory smart SL | per-trade loss budget <= {MAX_RISK_PER_TRADE_PCT:.2f}% equity | NO fixed aggregate position-count cap")
    print("[E | HIT & RUN EXECUTION] PURE VIRTUAL — Binance market data only")
    emit("BOT_ONLINE",reason="E_V17_2_FAST_VIRTUAL_STOP_EXECUTION_ACTIVE",payload={"engine_id":ENGINE_ID,"entry_paths":["HARMONIC","EXCEPTIONAL_COIN","MAJOR_STRUCTURAL_BREAKOUT"],"one_path_enough":True,"classical_removed":True,"stochrsi_role":"NOT_ENTRY_GATE","harmonic_model_frame":"5m","harmonic_execution_frame":"1m","harmonic_management_frame":"5m","structural_model_frame":"15m","structural_management_frame":"15m","entry_protection":True,"entry_protection_trigger_pct":30,"max_pretrigger_loss_usdt":3.0,"spot_long_only":True})
    snapshot(s,True)
    while True:
        started=time.time()
        try:
            reset_day(s); manage(s)
            # CONTINUOUS MODE: keep scanning/trading after 50+ closed trades.
            syms=universe(); qualified=[]; regime=market_regime(); diag={"candidate":0,"armed":0,"buy":0,"late":0}
            print(f"[E V16.9 REGIME] {regime['mode']} btc5m={regime['btc5']:+.2f}% btc15m={regime['btc15']:+.2f}% breadth={regime['breadth']:.1f}%")
            for i,sym in enumerate(syms):
                try:
                    setup=evaluate(sym,regime)
                    if setup:
                        st=str(setup.get("signal_state","DISCOVERED")).lower()
                        if st in diag: diag[st]+=1
                        if setup.get("late_chase"): diag["late"]+=1
                        h=setup.get("harmonic_assist",{}) or {}; ex=setup.get("exceptional_coin",{}) or {}
                        harmonic_scan=bool(h.get("long_alignment",False) and not setup.get("late_chase"))
                        exceptional_scan=bool(ex.get("exceptional",False) and not setup.get("late_chase"))
                        structural_scan=bool(ex.get("structural_signal",False) and not setup.get("late_chase"))
                        if harmonic_scan or exceptional_scan or structural_scan:
                            qualified.append(setup)
                            route="HARMONIC" if harmonic_scan else ("EXCEPTIONAL_COIN" if exceptional_scan else "MAJOR_STRUCTURAL_BREAKOUT")
                            print(f"[E V16.9 CANDIDATE] {sym} route={route} harmonic={harmonic_scan} exceptional={exceptional_scan} structural={structural_scan} ecm={float(ex.get('score',0) or 0):.1f} structure={float(ex.get('structural_score',0) or 0):.1f} signal={setup.get('signal_state')} opp={float(setup.get('opportunity_score',0) or 0):.1f}")
                except Exception as e:
                    if i<3: print("[SCAN WARN]",sym,str(e)[:90])
                if i%15==0: manage(s); snapshot(s)
            qualified.sort(key=lambda x:(max(float((x.get("harmonic_assist") or {}).get("confidence",0) or 0)*100.0,float((x.get("exceptional_coin") or {}).get("score",0) or 0),float((x.get("exceptional_coin") or {}).get("structural_score",0) or 0)),x.get("vol_ratio",0)),reverse=True)
            for setup in qualified:
                try_open(s,setup)
            manage(s); snapshot(s,True); save_state(s)
            print(f"[E V16.5 CYCLE] scanned={len(syms)} qualified={len(qualified)} buy={diag['buy']} armed={diag['armed']} candidate={diag['candidate']} late={diag['late']} open={len(s['positions'])} cash={s['strategy_cash']:.2f} equity={equity(s):.2f} realized_day={s['realized_day']:+.2f}")
        except Exception as e:
            print("[E | HIT & RUN LOOP ERROR]",repr(e)); emit("ERROR",reason=str(e)[:200])
        time.sleep(max(5,SCAN_SEC-(time.time()-started)))

if __name__=="__main__": main()
