import os
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
ECOS_KEY  = os.getenv("ECOS_API_KEY")
KOSIS_KEY = os.getenv("KOSIS_API_KEY")


def fetch_ecos():
    today = datetime.now().strftime('%Y%m%d')
    targets = [
        (f"722Y001/D/20210101/{today}/0101000", "Base Rate"),
        (f"731Y003/D/20210101/{today}/0000003", "Exchange Rate"),
        (f"151Y005/Q/2021Q1/2025Q4",            "Household Debt"),
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
            except (ValueError, AttributeError):
                continue

            # 날짜 파싱: 일별(YYYYMMDD), 분기별(YYYYQ1~Q4)
            if 'Q' in t:
                q_map = {'Q1': '03-31', 'Q2': '06-30', 'Q3': '09-30', 'Q4': '12-31'}
                suffix = next((v for k, v in q_map.items() if k in t), '12-31')
                date = f"{t[:4]}-{suffix}T00:00:00Z"
            else:
                date = f"{t[:4]}-{t[4:6]}-{t[6:8]}T00:00:00Z"

            results.append({
                "source":     "ECOS",
                "indicator":  name,
                "value":      val,
                "created_at": date,
            })
    return results


def fetch_kosis():
    """
    CPI 3종 (총지수·식료품·음식숙박) + 실업률 수집

    ▼ 수정 포인트
    - itmId=T  (기존 'T+' → 공백이 +로 인코딩되어 API 파라미터 오류)
    - objL2=0+A+K  (끝의 불필요한 '+' 제거)
    - C2 매핑: "0"→CPI_Total, "A"→CPI_Food, "K"→CPI_Restaurant
    """
    BASE = "https://kosis.kr/openapi/Param/statisticsParameterData.do"

    cpi_url = (
        f"{BASE}?method=getList&apiKey={KOSIS_KEY}"
        f"&itmId=T&objL1=T10+&objL2=0+A+K"          # ← itmId=T (공백 없음), objL2 끝 + 제거
        f"&format=json&jsonVD=Y&prdSe=M&newEstPrdCnt=100&orgId=101&tblId=DT_1J22001"
    )
    unemp_url = (
        f"{BASE}?method=getList&apiKey={KOSIS_KEY}"
        f"&itmId=T80+&objL1=ALL&objL2=00+"
        f"&format=json&jsonVD=Y&prdSe=M&newEstPrdCnt=100&orgId=101&tblId=DT_1DA7102S"
    )

    # C2 코드 → indicator 이름 매핑
    CPI_MAP = {
        "0": "CPI_Total",       # 총지수
        "A": "CPI_Food",        # 식료품 및 비주류음료
        "K": "CPI_Restaurant",  # 음식 및 숙박 (기존 CPI_Hotel → CPI_Restaurant 수정)
    }

    results = []

    # CPI
    try:
        cpi_data = requests.get(cpi_url, timeout=15).json()
        if not isinstance(cpi_data, list):
            logger.error(f"[KOSIS] CPI 응답 이상: {str(cpi_data)[:200]}")
        else:
            logger.info(f"[KOSIS] CPI 전체 행: {len(cpi_data)}")
            for d in cpi_data:
                c2  = (d.get('C2') or '').strip()
                ind = CPI_MAP.get(c2)
                if not ind:
                    continue  # 매핑 안 되는 코드는 스킵
                try:
                    val  = float(d['DT'])
                    prd  = d['PRD_DE']  # "YYYYMM"
                    date = f"{prd[:4]}-{prd[4:6]}-01T00:00:00Z"
                    results.append({"source": "KOSIS", "indicator": ind, "value": val, "created_at": date})
                except (KeyError, ValueError):
                    continue

            # C2 분포 로그 (디버깅용)
            from collections import Counter
            dist = Counter(d.get('C2','?') for d in cpi_data)
            logger.info(f"[KOSIS] CPI C2 분포: {dict(dist)}")
            for ind_name in CPI_MAP.values():
                cnt = sum(1 for r in results if r['indicator'] == ind_name)
                logger.info(f"  → {ind_name}: {cnt}건")
    except Exception as e:
        logger.error(f"[KOSIS] CPI 요청 실패: {e}")

    # 실업률
    try:
        unemp_data = requests.get(unemp_url, timeout=15).json()
        if not isinstance(unemp_data, list):
            logger.error(f"[KOSIS] 실업률 응답 이상: {str(unemp_data)[:200]}")
        else:
            logger.info(f"[KOSIS] 실업률: {len(unemp_data)}건")
            for d in unemp_data:
                try:
                    val  = float(d['DT'])
                    prd  = d['PRD_DE']
                    date = f"{prd[:4]}-{prd[4:6]}-01T00:00:00Z"
                    results.append({"source": "KOSIS", "indicator": "Unemployment Rate", "value": val, "created_at": date})
                except (KeyError, ValueError):
                    continue
    except Exception as e:
        logger.error(f"[KOSIS] 실업률 요청 실패: {e}")

    return results


def main():
    logger.info("=== 데이터 수집 시작 ===")
    data = fetch_ecos() + fetch_kosis()

    if not data:
        logger.warning("수집된 데이터 없음 — DB 업데이트 스킵")
        return

    # (indicator, created_at) 복합키로 중복 제거
    unique_data = list({(r['indicator'], r['created_at']): r for r in data}.values())
    logger.info(f"Upsert 준비: {len(unique_data)}건")

    # 500건씩 나눠서 upsert (Supabase 요청 크기 제한 대응)
    chunk = 500
    for i in range(0, len(unique_data), chunk):
        batch = unique_data[i:i + chunk]
        supabase.table("macro_indicators") \
            .upsert(batch, on_conflict="indicator,created_at") \
            .execute()
        logger.info(f"  [{i}~{i+len(batch)}] Upsert 완료")

    logger.info(f"✅ 총 {len(unique_data)}건 동기화 완료")


if __name__ == "__main__":
    main()
