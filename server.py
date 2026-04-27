import os
import logging
from flask import Flask, jsonify, send_from_directory
from dotenv import load_dotenv
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, 'dist')

app = Flask(__name__, static_folder=DIST_DIR, static_url_path='')

@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,OPTIONS'
    return response

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)


@app.route('/api/health')
def health():
    return jsonify({
        "status":      "ok",
        "dist_exists": os.path.exists(DIST_DIR),
        "dist_files":  os.listdir(DIST_DIR) if os.path.exists(DIST_DIR) else [],
    })


@app.route('/api/indicators/chart', methods=['GET'])
def get_chart_data():
    logger.info("--- 차트 데이터 요청 ---")
    try:
        res = (
            supabase.table("macro_indicators")
            .select("*")
            .order("created_at", desc=False)
            .range(0, 29999)
            .execute()
        )

        # ── indicator → data_map 키 매핑 ─────────────────────────────────
        # collector.py와 반드시 일치해야 함
        INDICATOR_MAP = {
            "Base Rate":         "bok_rate",
            "Exchange Rate":     "exch",
            "Household Debt":    "debt",
            "Unemployment Rate": "unemp",
            # CPI 3종: 각각 별도 키
            "CPI_Total":         "cpi_total",       # 총지수
            "CPI_Food":          "cpi_food",         # 식료품 및 비주류음료
            "CPI_Restaurant":    "cpi_restaurant",   # 음식 및 숙박
            # 하위 호환: 기존 DB에 CPI_Hotel로 저장된 데이터 대응
            "CPI_Hotel":         "cpi_restaurant",
            "CPI":               "cpi_total",        # 구버전 단일 CPI
        }

        data_map = {k: [] for k in set(INDICATOR_MAP.values())}

        for r in res.data:
            key = INDICATOR_MAP.get(r['indicator'])
            if key is None:
                continue

            raw_date = r.get('created_at', '')
            date_str = raw_date[:10] if raw_date else None
            if not date_str:
                continue

            data_map[key].append({"date": date_str, "value": r['value']})

        logger.info(
            f"전송 준비 — "
            f"금리:{len(data_map['bok_rate'])} "
            f"환율:{len(data_map['exch'])} "
            f"부채:{len(data_map['debt'])} "
            f"실업:{len(data_map['unemp'])} "
            f"CPI총:{len(data_map['cpi_total'])} "
            f"CPI식:{len(data_map['cpi_food'])} "
            f"CPI음:{len(data_map['cpi_restaurant'])}"
        )
        return jsonify({"success": True, "data": data_map})

    except Exception as e:
        logger.error(f"데이터 로드 에러: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    full = os.path.join(DIST_DIR, path)
    if path and os.path.exists(full):
        return send_from_directory(DIST_DIR, path)
    return send_from_directory(DIST_DIR, 'index.html')


application = app  # PythonAnywhere WSGI

if __name__ == "__main__":
    logger.info(f"서버 시작 — dist: {DIST_DIR} (존재: {os.path.exists(DIST_DIR)})")
    app.run(host='0.0.0.0', port=5000, debug=True)
