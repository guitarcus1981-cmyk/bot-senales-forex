import os
import requests
import pandas as pd
import yfinance as yf

# ------------------ CONFIGURACIÓN ------------------
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

PARES = ["EUR/USD=X", "GBP/USD=X", "USD/JPY=X", "AUD/USD=X", "USD/CAD=X", "USD/CHF=X", "NZD/USD=X"]
INTERVALO = "5m"
PERIODO_DESCARGA = "5d"
EMA_RAPIDA = 9
EMA_LENTA = 21
RSI_PERIODO = 14
RSI_SOBRECOMPRA = 70
RSI_SOBREVENTA = 30
MACD_RAPIDA = 12
MACD_LENTA = 26
MACD_SENAL = 9

# -----------------------------------------------------


def enviar_telegram(mensaje: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}, timeout=10)
        if not r.ok:
            print("Error enviando Telegram:", r.text)
    except Exception as e:
        print("Excepción enviando Telegram:", e)


def calcular_rsi(precios: pd.Series, periodo: int) -> pd.Series:
    delta = precios.diff()
    ganancia = delta.clip(lower=0)
    perdida = -delta.clip(upper=0)
    avg_gain = ganancia.rolling(periodo).mean()
    avg_loss = perdida.rolling(periodo).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calcular_macd(precios: pd.Series, rapida: int, lenta: int, senal: int):
    ema_rapida = precios.ewm(span=rapida, adjust=False).mean()
    ema_lenta = precios.ewm(span=lenta, adjust=False).mean()
    macd = ema_rapida - ema_lenta
    linea_senal = macd.ewm(span=senal, adjust=False).mean()
    histograma = macd - linea_senal
    return macd, linea_senal, histograma


def obtener_senal(simbolo: str):
    minimo_datos = max(EMA_LENTA, MACD_LENTA + MACD_SENAL) + 2
    df = yf.download(simbolo, period=PERIODO_DESCARGA, interval=INTERVALO, progress=False)
    if df.empty or len(df) < minimo_datos:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df["EMA_rapida"] = df["Close"].ewm(span=EMA_RAPIDA, adjust=False).mean()
    df["EMA_lenta"] = df["Close"].ewm(span=EMA_LENTA, adjust=False).mean()
    df["RSI"] = calcular_rsi(df["Close"], RSI_PERIODO)
    _, _, df["MACD_hist"] = calcular_macd(df["Close"], MACD_RAPIDA, MACD_LENTA, MACD_SENAL)

    ultima = df.iloc[-1]
    anterior = df.iloc[-2]

    cruce_alcista = anterior["EMA_rapida"] <= anterior["EMA_lenta"] and ultima["EMA_rapida"] > ultima["EMA_lenta"]
    cruce_bajista = anterior["EMA_rapida"] >= anterior["EMA_lenta"] and ultima["EMA_rapida"] < ultima["EMA_lenta"]

    rsi = ultima["RSI"]
    macd_hist = ultima["MACD_hist"]

    macd_confirma_alcista = macd_hist > 0
    macd_confirma_bajista = macd_hist < 0

    if cruce_alcista and rsi < RSI_SOBRECOMPRA and macd_confirma_alcista:
        return "CALL (compra)", ultima["Close"], rsi, macd_hist
    elif cruce_bajista and rsi > RSI_SOBREVENTA and macd_confirma_bajista:
        return "PUT (venta)", ultima["Close"], rsi, macd_hist

    return None


def ciclo():
    for par in PARES:
        try:
            resultado = obtener_senal(par)
            if resultado:
                direccion, precio, rsi, macd_hist = resultado
                nombre = par.replace("=X", "")
                nombre = f"{nombre[:3]}/{nombre[3:]}"
                emoji_direccion = "🟢" if "CALL" in direccion else "🔴"
                mensaje = (
                    f"Señal confirmada\n"
                    f"Par: {nombre}\n"
                    f"Dirección: {emoji_direccion} {direccion}\n"
                    f"Precio de cierre: {precio:.5f}\n"
                    f"Temporalidad: {INTERVALO}\n"
                    f"Apertura de la próxima vela"
                )
                print(mensaje)
                enviar_telegram(mensaje)
        except Exception as e:
            print(f"Error procesando {par}: {e}")


if __name__ == "__main__":
    print("Bot de señales - ejecución única (GitHub Actions)")
    ciclo()
