#!/usr/bin/env python3
"""
Render each SPDR/index tile to a portrait PNG for the Videri signage panels.
Shows TODAY's performance: current price, day change vs prior close, and the
intraday line. Data from Yahoo's public chart feed (works on GitHub Actions);
falls back to a demo intraday day if the network is unavailable.
Writes <SYMBOL>.png next to this script (repo root).
"""
import os, math, json, datetime
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Polygon
from matplotlib.ticker import FuncFormatter, MaxNLocator

BG="#0a0e17"; INK="#f4f6fb"; MUTED="#8b95ad"; UP="#39d98a"; DOWN="#ff5c6c"; GOLD="#c9a86a"; LINE="#1c2437"

SECTORS = {
    "SPY":("S&P 500",560),"QQQ":("Nasdaq 100",485),"DIA":("Dow 30",430),
    "XLK":("Technology",235),"XLF":("Financials",48),"XLV":("Health Care",145),
    "XLY":("Consumer Discretionary",205),"XLP":("Consumer Staples",82),"XLE":("Energy",92),
    "XLI":("Industrials",138),"XLB":("Materials",92),"XLU":("Utilities",78),
    "XLRE":("Real Estate",42),"XLC":("Communications",102),"GLD":("Gold",245),
}

def now_et():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.datetime.utcnow()

# ---- deterministic RNG for the demo fallback ----
def _seed(s):
    h=2166136261
    for ch in s:
        h^=ord(ch); h=(h*16777619)&0xFFFFFFFF
    return h
def _mulberry32(a):
    a&=0xFFFFFFFF
    def rnd():
        nonlocal a
        a=(a+0x6D2B79F5)&0xFFFFFFFF; t=a
        t=((t^(t>>15))*(t|1))&0xFFFFFFFF
        t^=(t+(((t^(t>>7))*(t|61))&0xFFFFFFFF))&0xFFFFFFFF
        return ((t^(t>>14))&0xFFFFFFFF)/4294967296
    return rnd

def demo_day(symbol, level, n=78):
    """One intraday session, small realistic move."""
    r=_mulberry32(_seed(symbol+now_et().strftime("%Y%m%d")))
    prev=level*(0.95+r()*0.10)
    day=r()*0.03-0.012          # -1.2% .. +1.8% on the day
    amp=0.003+r()*0.004; f=2+r()*3; ph=r()*2*math.pi
    closes=[]
    for i in range(n):
        t=i/(n-1)
        base=prev*(1+day*t)
        wig=amp*math.sin(f*2*math.pi*t+ph)+(r()-0.5)*0.0016
        closes.append(base*(1+wig))
    return closes, closes[-1], prev, False

def yahoo_day(symbol):
    """(closes, price, prev_close, True) from Yahoo intraday, or None."""
    try:
        import urllib.request
        url=(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
             f"?interval=5m&range=1d")
        req=urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        j=json.loads(urllib.request.urlopen(req, timeout=25).read().decode())
        res=j["chart"]["result"][0]; meta=res["meta"]
        prev=meta.get("chartPreviousClose") or meta.get("previousClose")
        price=meta.get("regularMarketPrice")
        q=res["indicators"]["quote"][0]["close"]
        closes=[c for c in q if c is not None]
        if not closes or not prev:
            return None
        if price is None: price=closes[-1]
        return closes, float(price), float(prev), True
    except Exception:
        return None

def get_data(symbol, level):
    return yahoo_day(symbol) or demo_day(symbol, level)

def fmt(v):
    v=abs(v)
    return format(v,",.0f") if v>=1000 else format(v,",.2f")

def spaced(s): return " ".join(list(s))

def gradient_fill(ax,x,y,color,y0):
    grad=np.empty((100,1,4)); grad[:,:,:3]=mcolors.to_rgb(color)
    grad[:,:,-1]=np.linspace(0.42,0.0,100)[:,None]
    im=ax.imshow(grad,aspect="auto",origin="upper",extent=[min(x),max(x),y0,max(y)],zorder=1)
    verts=[(min(x),y0)]+list(zip(x,y))+[(max(x),y0)]
    clip=Polygon(verts,closed=True,facecolor="none",edgecolor="none")
    ax.add_patch(clip); im.set_clip_path(clip)

def render(symbol, outdir):
    name, level = SECTORS[symbol]
    closes, price, prev, real = get_data(symbol, level)
    chg = (price - prev) / prev * 100.0
    up = chg >= 0
    col = UP if up else DOWN
    hi, lo = max(closes+[prev]), min(closes+[prev])
    arrow = "▲" if up else "▼"; sign = "+" if up else ""

    W,H=1080,1920
    fig=plt.figure(figsize=(W/100,H/100),dpi=100); fig.patch.set_facecolor(BG)
    L,R=0.075,0.925
    fig.text(L+0.018,0.958,spaced("VENTURE VISIONARY PARTNERS"),color=MUTED,fontsize=15,fontweight="bold",va="center")
    fig.text(L,0.958,"●",color=GOLD,fontsize=13,va="center")
    fig.text(R,0.958,spaced("SECTOR BOARD"),color=MUTED,fontsize=15,fontweight="bold",va="center",ha="right")
    fig.text(L,0.885,symbol,color=INK,fontsize=118,fontweight="bold",va="center")
    fig.text(L+0.004,0.828,spaced(name.upper()),color=MUTED,fontsize=27,va="center")
    pt=fig.text(L,0.762,fmt(price),color=INK,fontsize=76,fontweight="bold",va="center")
    fig.canvas.draw(); bb=pt.get_window_extent(renderer=fig.canvas.get_renderer())
    fig.text(bb.x1/W+0.03,0.762,arrow+" "+sign+format(chg,".2f")+"%",color=col,fontsize=34,fontweight="bold",va="center")
    fig.text(L,0.718,"Today",color=MUTED,fontsize=22,va="center")

    ax=fig.add_axes([L,0.13,0.775,0.55]); ax.set_facecolor(BG)
    x=np.arange(len(closes)); pad=(hi-lo)*0.15 or (abs(price)*0.002 or 1); y0=lo-pad
    ax.set_ylim(y0,hi+pad); ax.set_xlim(0,max(1,len(closes)-1))
    # prior-close baseline
    ax.axhline(prev, color=MUTED, linewidth=1.1, linestyle=(0,(4,4)), alpha=0.5, zorder=2)
    ax.plot(x,closes,color=col,linewidth=3.2,solid_capstyle="round",zorder=3)
    gradient_fill(ax,x,np.array(closes),col,y0)
    ax.yaxis.tick_right()
    for sp in ax.spines.values(): sp.set_visible(False)
    ax.set_xticks([]); ax.grid(axis="y",color=LINE,linewidth=1.2)
    ax.tick_params(axis="y",colors=MUTED,labelsize=16,length=0)
    ax.yaxis.set_major_locator(MaxNLocator(5)); ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_:fmt(v)))

    fig.text(L,0.062,spaced("VVP"),color=GOLD,fontsize=16,fontweight="bold",va="center")
    fig.text(0.19,0.062,"H "+fmt(hi)+"   L "+fmt(lo)+"   Prev "+fmt(prev),color=MUTED,fontsize=15,va="center")
    fig.text(R,0.062,now_et().strftime("as of %-I:%M %p ET"),color=MUTED,fontsize=15,va="center",ha="right")

    os.makedirs(outdir,exist_ok=True)
    fig.savefig(os.path.join(outdir,symbol+".png"),facecolor=BG,dpi=100); plt.close(fig)
    return chg, real

if __name__=="__main__":
    here=os.path.dirname(os.path.abspath(__file__))
    for s in SECTORS:
        ch,real=render(s,here)
        print(f"{s:5} {ch:+6.2f}%  {'live' if real else 'demo'}")
    print("done")
