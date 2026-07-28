import pandas as pd
from config import settings
from strategy import add_indicators, confirmed_pivots, trend_side

def run():
    assert settings.main_swing_min_atr > 0
    idx=pd.date_range('2026-01-01', periods=30, freq='1h', tz='UTC')
    close=pd.Series(range(100,130), index=idx, dtype=float)
    df=pd.DataFrame({'open':close-0.2,'high':close+1,'low':close-1,'close':close,'volume':1.0})
    out=add_indicators(df)
    assert 'atr14' in out and 'ema200' in out
    row=pd.Series({'close':120,'ema50':110,'ema100':100,'ema200':90})
    assert trend_side(row,0)=='buy'
    piv=confirmed_pivots(df,2,2)
    assert isinstance(piv,list)
    print('Structural tests passed.')
if __name__=='__main__': run()
