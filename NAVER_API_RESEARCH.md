# Naver Finance API Endpoint Research

> Tested: 2026-03-30
> All endpoints are **unauthenticated** (no API key required)
> No rate limit headers observed; expected to be reasonable for personal use

---

## API Base URLs

| Name | URL | Used For |
|------|-----|----------|
| Stock Mobile API | `https://m.stock.naver.com/api/` | Korean stock basic/integration, domestic index basic |
| Stock Server API | `https://api.stock.naver.com/` | Chart data, exchanges list, foreign index list |
| Polling API | `https://polling.finance.naver.com/` | Real-time price updates |
| Front API (BFF) | `https://m.stock.naver.com/front-api/` | Exchange rates, commodities, bonds, crypto |
| Legacy Finance | `https://finance.naver.com/api/` | ETF list |
| Legacy Chart (XML) | `https://fchart.stock.naver.com/` | Historical OHLCV (XML format) |
| Legacy Chart (JSON) | `https://api.finance.naver.com/siseJson.naver` | Historical OHLCV (JSON-like array) |

---

## 1. Korean Stock - Basic Info [WORKS]

### `GET m.stock.naver.com/api/stock/{itemCode}/basic`

**Example:** `https://m.stock.naver.com/api/stock/005930/basic`

**Key Fields:**
- `stockName` - 종목명 (삼성전자)
- `closePrice` - 현재가/종가 (formatted string: "176,300")
- `compareToPreviousClosePrice` - 전일대비 ("-3,400")
- `compareToPreviousPrice.name` - RISING/FALLING/UNCHANGED
- `fluctuationsRatio` - 등락률 ("-1.89")
- `marketStatus` - OPEN/CLOSE
- `localTradedAt` - 마지막 거래시간 (ISO 8601)
- `stockExchangeType.name` - KOSPI/KOSDAQ
- `overMarketPriceInfo` - 시간외 거래 정보
  - `overPrice`, `fluctuationsRatio`, `overMarketStatus`
- `delayTime` - 0 (실시간)

---

## 2. Korean Stock - Integration (Comprehensive) [WORKS]

### `GET m.stock.naver.com/api/stock/{itemCode}/integration`

**Example:** `https://m.stock.naver.com/api/stock/005930/integration`

**Key Fields:**
- `totalInfos[]` - Array of key metrics:
  - `lastClosePrice` (전일), `openPrice` (시가), `highPrice` (고가), `lowPrice` (저가)
  - `accumulatedTradingVolume` (거래량), `accumulatedTradingValue` (대금)
  - `marketValue` (시총: "1,043조 6,322억")
  - `foreignRate` (외인소진율: "48.70%")
  - `highPriceOf52Weeks`, `lowPriceOf52Weeks` (52주 최고/최저)
  - `per` (PER: "26.86배"), `eps` (EPS), `cnsPer` (추정PER), `cnsEps` (추정EPS)
  - `pbr` (PBR), `bps` (BPS)
  - `dividendYieldRatio` (배당수익률), `dividend` (주당배당금)
- `dealTrendInfos[]` - 최근 5일 투자자별 매매동향:
  - `foreignerPureBuyQuant` (외국인 순매수)
  - `organPureBuyQuant` (기관 순매수)
  - `individualPureBuyQuant` (개인 순매수)
  - `foreignerHoldRatio` (외국인 보유비율)
- `researches[]` - 최근 증권사 리서치 리포트
- `consensusInfo` - 컨센서스:
  - `recommMean`, `priceTargetMean` (목표가 평균)
- `industryCompareInfo[]` - 동종업종 비교 종목

> **NOTE:** This single endpoint replaces the need for separate investor flow and consensus endpoints.

---

## 3. Korean Stock - Chart Data [WORKS]

### `GET api.stock.naver.com/chart/domestic/item/{itemCode}?periodType={type}`

**Period Types:** `dayCandle`, `weekCandle`, `monthCandle`

**Optional params:** `startDateTime=YYYYMMDD`, `endDateTime=YYYYMMDD`

**Example:** `https://api.stock.naver.com/chart/domestic/item/005930?periodType=dayCandle&startDateTime=20260301&endDateTime=20260330`

**Key Fields per priceInfo:**
- `localDate` - 날짜 (YYYYMMDD)
- `closePrice`, `openPrice`, `highPrice`, `lowPrice` - OHLC (numeric, not string)
- `accumulatedTradingVolume` - 거래량
- `foreignRetentionRate` - 외국인 보유율

**Data range:** ~110 trading days for dayCandle (when no date range specified), ~2 years for weekCandle, ~9 years for monthCandle

> **NOTE:** 5-minute candle (`candleMinuteFive`) returns empty. Intraday data not available via this API.

---

## 4. Real-time Price - Polling [WORKS]

### `GET polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{itemCode}`

**Example:** `https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:005930`

**Key Fields (in result.areas[0].datas[0]):**
- `cd` - 종목코드
- `nv` - 현재가 (numeric: 176300)
- `sv` - 전일가
- `cv` - 전일대비
- `cr` - 등락률
- `rf` - 상승/하락 코드 ("2"=상승, "5"=하락)
- `ov` - 시가, `hv` - 고가, `lv` - 저가
- `aq` - 거래량, `aa` - 거래대금
- `eps`, `bps`, `keps`, `cnsEps`, `dv` (배당금)
- `countOfListedStock` - 상장주식수
- `ms` - OPEN/CLOSE
- `nxtOverMarketPriceInfo` - 시간외 거래 정보
- `pollingInterval` - 추천 폴링 간격 (70000ms = 70초)

### `GET polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:{indexCode}`

**Example:** `https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:KOSPI`

**Key Fields:**
- `nv` - 현재지수 (527730 = 5277.30), `cv` - 전일대비, `cr` - 등락률
- `ov` - 시가, `hv` - 고가, `lv` - 저가

---

## 5. Korean Indices (KOSPI, KOSDAQ) [WORKS]

### Basic Info: `GET m.stock.naver.com/api/index/{indexCode}/basic`

**Codes:** `KOSPI`, `KOSDAQ`

**Key Fields:** Same structure as stock basic - `closePrice`, `fluctuationsRatio`, `marketStatus`, etc.

### Chart Data: `GET api.stock.naver.com/chart/domestic/index/{indexCode}?periodType={type}`

**Example:** `https://api.stock.naver.com/chart/domestic/index/KOSPI?periodType=dayCandle`

**Key Fields:** Same as stock chart - `localDate`, OHLC, `accumulatedTradingVolume`

---

## 6. US/Foreign Stock Chart Data [WORKS]

### `GET api.stock.naver.com/chart/foreign/item/{reutersCode}?periodType={type}`

**Example:** `https://api.stock.naver.com/chart/foreign/item/NVDA.O?periodType=dayCandle`

**Reuters Code Format:** `TICKER.EXCHANGE` (e.g., `NVDA.O` for NASDAQ, `AAPL.O`)

**Key Fields per priceInfo:**
- `localDate`, `closePrice`, `openPrice`, `highPrice`, `lowPrice` (decimal, e.g., 167.885)
- `accumulatedTradingVolume`
- `decimalUnit: 2` (2 decimal places for USD prices)

> **NOTE:** `m.stock.naver.com/api/stock/{reutersCode}/basic` returns HTTP 400 for US stocks. Basic info for US stocks is NOT available via this endpoint. Use the chart endpoint or integration page scraping instead.

---

## 7. Foreign Index List & Data [WORKS]

### List by Nation: `GET api.stock.naver.com/index/nation/{nationCode}`

**Example:** `https://api.stock.naver.com/index/nation/USA`

Returns all indices for a nation with real-time data. USA indices include:
- `.DJI` - DowJones Industrial (다우존스)
- `.IXIC` - NASDAQ Composite (나스닥 종합)
- `.INX` - S&P 500
- `.NDX` - NASDAQ 100
- `.SOX` - Philadelphia Semiconductor (필라델피아 반도체)
- `.VIX` - CBOE VIX Index (VIX)

**Key Fields per index:**
- `reutersCode` - 로이터 코드 (e.g., ".DJI")
- `indexName` / `indexNameEng` - 지수명
- `closePrice` - 현재가 (formatted string)
- `lastClosePrice` - 전일가 (numeric)
- `compareToPreviousClosePrice` - 전일대비
- `fluctuationsRatio` - 등락률
- `marketStatus` - OPEN/CLOSE
- `delayTime` - 0 for US major indices (실시간), 15 for VIX
- `highPriceOf52Weeks`, `lowPriceOf52Weeks`

### Chart: `GET api.stock.naver.com/chart/foreign/index/{reutersCode}?periodType={type}`

**Example:** `https://api.stock.naver.com/chart/foreign/index/.INX?periodType=dayCandle`

---

## 8. Exchange List [WORKS]

### `GET api.stock.naver.com/stock/exchanges`

Returns list of all supported stock exchanges:
- USA: NYSE (`NYS`), NASDAQ (`NSQ`), AMEX (`AMX`)
- China: Shanghai (`SHH`), Shenzhen (`SHZ`)
- Hong Kong: (`HKG`)
- Japan: Tokyo (`TYO`)
- Vietnam: Ho Chi Minh (`HSX`), Hanoi (`HNX`)

---

## 9. Exchange Rates [WORKS]

### Main Exchange Rates: `GET m.stock.naver.com/front-api/marketIndex/exchange/main`

Returns grouped data with `exchange` (vs KRW) and `exchangeWorld` (cross rates):

**Key Fields:**
- `name` - "미국 USD", "유럽 EUR", etc.
- `closePrice` - "1,519.60" (KRW per unit)
- `fluctuations`, `fluctuationsRatio`
- `reutersCode` - `FX_USDKRW`, `FX_EURKRW`, `FX_JPYKRW`, `FX_CNYKRW`
- `marketStatus` - OPEN/CLOSE
- `categoryType` - "exchange" or "exchangeWorld"

### All Exchange Rates: `GET m.stock.naver.com/front-api/marketIndex/exchange/new`

Returns comprehensive list of all currencies vs KRW + Dollar Index (`.DXY`)

### Exchange Code List: `GET m.stock.naver.com/front-api/marketIndex/exchange/exchangeCodes`

### World Cross Rates: `GET m.stock.naver.com/front-api/marketIndex/exchange/world`

### Bank Rates: `GET m.stock.naver.com/front-api/marketIndex/exchange/bank`

> **NOTE:** Historical chart data for exchange rates is NOT available via API. The `api.stock.naver.com/chart/` endpoints do not support exchange rate symbols.

---

## 10. Commodities - Energy [WORKS]

### `GET m.stock.naver.com/front-api/marketIndex/energy`

Returns oil and energy futures with `mainList` and `chartList`:

**Items include:**
- WTI (symbolCode: `CL`, reutersCode: `CLcv1`)
- Brent (symbolCode: `BRN`, reutersCode: `LCOcv1`)
- RBOB Gasoline, Heating Oil, Natural Gas

**Key Fields:**
- `name`, `closePrice`, `fluctuations`, `fluctuationsRatio`
- `unit` - "USD/BBL"
- `delayTime` - 10 (10-minute delay)
- `month` - futures contract month

---

## 11. Commodities - Metals [WORKS]

### `GET m.stock.naver.com/front-api/marketIndex/metals`

**Items include:**
- International Gold (symbolCode: `GC`, reutersCode: `GCcv1`) - USD/OZS
- Domestic Gold (`M04020000`) - KRW/g (실시간)
- Silver (symbolCode: `SI`) - USD/OZS
- Copper futures, Platinum, Palladium

---

## 12. Bond Yields [WORKS]

### Main Bond Yields: `GET m.stock.naver.com/front-api/marketIndex/bondMain`

Returns major global bond yields:
- 미국 국채 10년 (`US10YT=RR`) - real-time
- 한국 국채 10년 (`KR10YT=RR`) - real-time
- 일본 국채 10년, 독일 국채 10년, etc.

### Bond by Country: `GET m.stock.naver.com/front-api/marketIndex/bondList?countryCode={code}`

**Example:** `https://m.stock.naver.com/front-api/marketIndex/bondList?countryCode=USA`

Returns US Treasury yields across all maturities:
- 2Y, 3Y, 5Y, 10Y, 30Y

### Bond Nation List: `GET m.stock.naver.com/front-api/marketIndex/bondNation`

Returns list of 17 countries with bond data (USA, KOR, EUR, GBR, JPN, CHN, DEU, etc.)

### Domestic Interest Rates: `GET m.stock.naver.com/front-api/marketIndex/domesticInterestList`

### Standard Interest Rates: `GET m.stock.naver.com/front-api/marketIndex/standardInterestList`

---

## 13. Major Market Overview [WORKS]

### `GET m.stock.naver.com/front-api/marketIndex/majors`

Returns grouped overview of all major market indicators:
- `exchange` - Dollar Index + major FX rates
- `exchangeWorld` - Cross rates
- `metals` - Gold, Silver
- `energy` - WTI, Brent
- `bond` - US 10Y, KR 10Y, etc.
- `domesticInterest` - Korean interest rates
- `standardInterest` - Central bank rates

---

## 14. Crypto (Bitcoin, etc.) [WORKS]

### Top Crypto List: `GET m.stock.naver.com/front-api/crypto/top?exchangeType={exchange}`

**exchangeType:** `UPBIT` or `BITHUMB`

**Supports pagination:** `sortType=marketCap&page=1&pageSize=20`

**Key Fields per coin:**
- `nfTicker` - BTC, ETH, XRP, etc.
- `krName` - 비트코인, 이더리움, etc.
- `tradePrice` - 현재가 (numeric KRW: 102325000)
- `change` - RISING/FALLING
- `changeRate` - 등락률 (1.94)
- `changeValue` - 전일대비
- `marketCap` - 시가총액
- `accumulatedTradingVolume`, `accumulatedTradingValue`
- `krwPremiumRate` - 김치프리미엄 (-0.34)
- `formatted.*` - Formatted string versions of all fields

> **NOTE:** Prices are from Korean exchanges (Upbit/Bithumb) in KRW. The `krwPremiumRate` field shows the kimchi premium vs global prices.

---

## 15. ETF List [WORKS]

### `GET finance.naver.com/api/sise/etfItemList.nhn`

Returns all Korean ETFs with real-time data (requires no parameters).

---

## 16. Legacy Historical Data [WORKS]

### fchart (XML): `GET fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe={tf}&count={n}&requestType=0`

- `timeframe`: day, week, month
- Format: XML with `<item data="DATE|OPEN|HIGH|LOW|CLOSE|VOLUME" />`
- Only works for Korean stock codes (not FX or foreign stocks)

### siseJson (JSON-like): `GET api.finance.naver.com/siseJson.naver?symbol={code}&requestType=1&startTime=YYYYMMDD&endTime=YYYYMMDD&timeframe=day`

- Returns data as array-of-arrays (not strict JSON)
- Fields: 날짜, 시가, 고가, 저가, 종가, 거래량, 외국인소진율
- Only works for Korean stock codes

---

## ENDPOINTS THAT DO NOT WORK

| Endpoint | Status | Notes |
|----------|--------|-------|
| `m.stock.naver.com/api/stock/{US_CODE}/basic` | 400 | US stock basic info not available via this API |
| `m.stock.naver.com/api/exchange/FX_USDKRW/basic` | 404 | Use front-api instead |
| `m.stock.naver.com/api/crypto/BTC/basic` | 404 | Use front-api/crypto/top instead |
| `m.stock.naver.com/api/commodity/GC/basic` | 404 | Use front-api/marketIndex/metals |
| `m.stock.naver.com/api/stock/005930/investor` | 404 | Investor data is in /integration endpoint |
| `m.stock.naver.com/api/index/SPX/basic` | 409 | Use api.stock.naver.com/index/nation/USA |
| `api.stock.naver.com/chart/exchange/FX_USDKRW` | 404 | No historical chart for FX |
| `api.stock.naver.com/chart/domestic/marketIndex/FX_USDKRW` | empty | Not supported |
| `polling...?query=SERVICE_EXCHANGE:FX_USDKRW` | empty | Not a supported service type |
| `finance.naver.com/api/sise/marketIndex.nhn` | 404 | Old endpoint removed |
| Intraday 5-min candle | empty | Returns 0 records outside market hours |

---

## COVERAGE SUMMARY: Naver vs yfinance

### What Naver covers well (USE NAVER):
- **Korean stocks:** Real-time price, OHLCV charts, fundamentals (PER/PBR/EPS), investor flow, consensus
- **Korean indices:** KOSPI, KOSDAQ real-time + historical chart
- **Foreign indices:** DJI, NASDAQ, S&P500, SOX, VIX -- real-time via `api.stock.naver.com/index/nation/USA`
- **Exchange rates:** All major currencies vs KRW, cross rates (current price only)
- **Commodities:** Gold, Silver, WTI, Brent (current price, 10-min delay)
- **Bond yields:** US Treasury (2Y-30Y), Korean bonds, global bonds -- real-time
- **Crypto:** BTC, ETH, XRP etc. via Upbit/Bithumb in KRW with kimchi premium
- **ETF list:** Korean ETFs with real-time prices

### What Naver does NOT cover (NEED yfinance or other):
- **US stock basic info:** No basic/fundamental endpoint (PER, EPS, market cap) for US stocks
- **Historical exchange rate charts:** No OHLCV history for FX pairs
- **Historical commodity charts:** No OHLCV history for gold/oil
- **Historical bond yield charts:** No time-series for bond yields
- **Historical crypto charts:** No OHLCV chart for crypto prices
- **US stock intraday data:** 5-min candle returns empty for foreign stocks
- **Dividend history / earnings calendar:** Not available as dedicated endpoints

### Recommended Hybrid Strategy:
1. **Korean stocks + indices:** 100% Naver (superior data: investor flow, consensus, real-time)
2. **US stock charts:** Naver `api.stock.naver.com/chart/foreign/item/` (real-time, no auth)
3. **US stock fundamentals:** yfinance (PER, EPS, market cap for US stocks)
4. **FX/Commodity/Bond current price:** Naver front-api
5. **FX/Commodity/Bond historical:** yfinance
6. **Crypto current:** Naver front-api/crypto/top (KRW prices with premium data)
7. **Crypto historical:** yfinance or exchange API
