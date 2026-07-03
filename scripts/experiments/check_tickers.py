import yfinance as yf
symbols = ["INDEGENE.NS", "INDGN.NS", "INGENE.NS", "INDGENE.NS", "INDGN.BO"]
for s in symbols:
    df = yf.download(s, period="5d", progress=False)
    print(f"{s}: empty={df.empty}, shape={df.shape}")
