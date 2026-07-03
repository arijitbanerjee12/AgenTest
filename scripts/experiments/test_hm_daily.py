"""Quick test: HM daily signals for all 10 symbols."""
from agentest.utils.indicators.btst import get_today_signal_hm, HM_SYMBOLS
for s in HM_SYMBOLS:
    sig = get_today_signal_hm(s["symbol"], s["name"], s["category"], "15m")
    if sig:
        print(f"{s['name']:<14} {sig['signal']:<6} RSI9={sig['rsi9']:<6} Speed={sig['speed']:<6} Strength={sig['strength']:<6} {sig['reason']}")
    else:
        print(f"{s['name']:<14} NO DATA")
