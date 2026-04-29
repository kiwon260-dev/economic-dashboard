import os
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from collections import Counter

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
ECOS_KEY  = os.getenv("ECOS_API_KEY")
KOSIS_KEY = os.getenv("KOSIS_API_KEY")
FRED_KEY  = "2b48449323afe69823ebbbe1042e3ac0"


# ─────────────────────────────────────────────
# ECOS (한국은행)
# ─────────────────────────────────────────────
def fetch_ecos():
    today = datetime.now().strftime('%Y%m%d')

    targets = [
        (f"722Y001/D/20210101/{today}/0101000", "Base Rate"),
        (f"731Y003/D/20210101/{today}/0000003", "Exchange Rate"),
        (f"151Y005/Q/2021Q1/2025Q4", "Household Debt"),
    ]

    results = []

    for path, name in targets:
        url = f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}/json/kr/1/10000/{path}"

        try:
            res = requests.get(url, timeout=15).json()
        except Exception as e:
            logger.error(f"[ECOS] {name} 요청 실패: {e}")
            continue

        rows = res.get('StatisticSearch', {}).get('row', [])
        logger.info(f"[ECOS] {name}: {len(rows)}건")

        for r in rows:
            t = r['TIME']

            try:
                val = float(r['DATA_VALUE'].replace(',', ''))
            except:
                continue

            if 'Q' in t:
                q_map = {'Q1':'03-31','Q2':'06-30','Q3':'09-30','Q4':'12-31'}
                suffix = next((v for k,v in q_map.items() if k in t),'12-31')
                date = f"{t[:4]}-{suffix}T00:00:00Z"
            else:
                date = f"{t[:4]}-{t[4:6]}-{t[6:8]}T00:00:00Z"

            results.append({
                "source": "ECOS",
                "indicator": name,
                "value": val,
                "created_at": date
            })

    logger.info(f"[ECOS] 총 데이터: {len(results)}건")
    return results


# ─────────────────────────────────────────────
# KOSIS (물가 + 실업률)
# ─────────────────────────────────────────────
def fetch_kosis():
    BASE = "https://kosis.kr/openapi/Param/statisticsParameterData.do"

    cpi_url = (
        f"{BASE}?method=getList&apiKey={KOSIS_KEY}"
        f"&itmId=T&objL1=T10+&objL2=0+A+K"
        f"&format=json&jsonVD=Y&prdSe=M&newEstPrdCnt=100&orgId=101&tblId=DT_1J22001"
    )

    unemp_url = (
        f"{BASE}?method=getList&apiKey={KOSIS_KEY}"
        f"&itmId=T80+&objL1=ALL&objL2=00+"
        f"&format=json&jsonVD=Y&prdSe=M&newEstPrdCnt=100&orgId=101&tblId=DT_1DA7102S"
    )

    CPI_MAP = {"0":"CPI_Total","A":"CPI_Food","K":"CPI_Restaurant"}
    results = []

    # CPI
    try:
        data = requests.get(cpi_url, timeout=15).json()
        logger.info(f"[KOSIS] CPI: {len(data)}건")

        for d in data:
            c2 = (d.get('C2') or '').strip()
            ind = CPI_MAP.get(c2)
            if not ind:
                continue

            try:
                val = float(d['DT'])
                prd = d['PRD_DE']
                date = f"{prd[:4]}-{prd[4:6]}-01T00:00:00Z"

                results.append({
                    "source":"KOSIS",
                    "indicator":ind,
                    "value":val,
                    "created_at":date
                })
            except:
                continue

    except Exception as e:
        logger.error(f"[KOSIS] CPI 실패: {e}")

    # 실업률
    try:
        data = requests.get(unemp_url, timeout=15).json()
        logger.info(f"[KOSIS] 실업률: {len(data)}건")

        for d in data:
            try:
                val = float(d['DT'])
                prd = d['PRD_DE']
                date = f"{prd[:4]}-{prd[4:6]}-01T00:00:00Z"

                results.append({
                    "source":"KOSIS",
                    "indicator":"Unemployment Rate",
                    "value":val,
                    "created_at":date
                })
            except:
                continue

    except Exception as e:
        logger.error(f"[KOSIS] 실업률 실패: {e}")

    logger.info(f"[KOSIS] 총 데이터: {len(results)}건")
    return results


# ─────────────────────────────────────────────
# FRED (미국 금리)
# ─────────────────────────────────────────────
def fetch_intl_rates():
    url = (
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id=FEDFUNDS"
        f"&api_key={FRED_KEY}"
        f"&file_type=json"
    )

    results = []

    try:
        res = requests.get(url, timeout=15).json()
        rows = res.get("observations", [])

        logger.info(f"[FRED] 미국금리: {len(rows)}건")

        for r in rows:
            if r["value"] == ".":
                continue

            try:
                val = float(r["value"])
                date = f"{r['date']}T00:00:00Z"

                results.append({
                    "source": "FRED",
                    "indicator": "IntRate_US",
                    "value": val,
                    "created_at": date
                })
            except:
                continue

    except Exception as e:
        logger.error(f"[FRED] 실패: {e}")

    logger.info(f"[FRED] 총 데이터: {len(results)}건")
    return results


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    logger.info("=== 데이터 수집 시작 ===")

    data = fetch_ecos() + fetch_kosis() + fetch_intl_rates()

    if not data:
        logger.warning("데이터 없음")
        return

    logger.info(f"전체 데이터 수: {len(data)}건")

    # 지표별 개수
    cnt = Counter(r['indicator'] for r in data)
    logger.info(f"지표별 개수: {dict(cnt)}")

    # 샘플
    for r in data[:5]:
        logger.info(f"샘플: {r}")

    unique_data = list({(r['indicator'], r['created_at']): r for r in data}.values())

    chunk = 500
    for i in range(0, len(unique_data), chunk):
        supabase.table("macro_indicators") \
            .upsert(unique_data[i:i+chunk], on_conflict="indicator,created_at") \
            .execute()

    logger.info(f"✅ 총 {len(unique_data)}건 업로드 완료")


if __name__ == "__main__":
    main()