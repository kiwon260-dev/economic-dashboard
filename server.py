from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import requests, urllib3, os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
dist_path = os.path.join(BASE_DIR, 'dist')
IS_PROD = os.path.isdir(dist_path)

app = Flask(
    __name__,
    static_folder=dist_path if IS_PROD else None,
    static_url_path='' if IS_PROD else None,
)
CORS(app)

BOK_KEY   = "9PDUTTQC3QYSL870G1AX"
KOSIS_KEY = "NzllNGQwYjExYTI4ZWQ0NzhiZWNiNDAyYTAyNzNhODk="

def safe_get(name, url, default_type="dict"):
    print(f"📡 [요청 시도] {name} 데이터...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        r = requests.get(url, timeout=10, verify=False, headers=headers)
        if r.status_code == 200:
            print(f"✅ [성공] {name}")
            return r.json()
    except Exception as e:
        print(f"🔥 [에러] {name}: {str(e)}")
    
    # 실패 시 프론트엔드가 에러 나지 않게 빈 구조 반환
    return [] if default_type == "list" else {"StatisticSearch": {"row": []}}

@app.route('/api/economic-data')
def get_economic_data():
    print("\n🚀 [API 호출 수신]")
    
    # 1. 한국은행 데이터 (원래 나오던 이름으로 복구)
    # GDP 대신 금리를 넣으셨던 것 같아 금리 데이터를 'bok_gdp' 키에 일단 같이 보냅니다.
    bok_gdp = safe_get("금리/GDP", f"https://ecos.bok.or.kr/api/StatisticSearch/{BOK_KEY}/json/kr/1/10/722Y001/M/202301/202512/0101000")
    bok_debt = safe_get("부채", f"https://ecos.bok.or.kr/api/StatisticSearch/{BOK_KEY}/json/kr/1/10/151Y005/Q/2023Q1/2025Q4")
    
    # 추가 데이터 (환율 등 )
    exchange_rate = safe_get("환율", f"https://ecos.bok.or.kr/api/StatisticSearch/{BOK_KEY}/json/kr/1/10/731Y001/D/20240101/20251231/0000001")

    # 2. 통계청 데이터 (리스트 형식으로 반환되므로 실패 시 [] 반환하도록 설정)
    unemp = safe_get("실업", f"https://kosis.kr/openapi/Param/statisticsParameterData.do?method=getList&apiKey={KOSIS_KEY}&itmId=T80+&objL1=ALL&objL2=00+&format=json&jsonVD=Y&prdSe=M&newEstPrdCnt=10&orgId=101&tblId=DT_1DA7102S", "list")
    cpi = safe_get("물가", f"https://kosis.kr/openapi/Param/statisticsParameterData.do?method=getList&apiKey={KOSIS_KEY}&itmId=T&objL1=T10+&objL2=0+A+K&format=json&jsonVD=Y&prdSe=M&newEstPrdCnt=10&orgId=101&tblId=DT_1J22001", "list")

    response = {
        "bok_gdp": bok_gdp,
        "bok_debt": bok_debt,
        "exchange_rate": exchange_rate,
        "unemp": unemp,
        "cpi": cpi
    }
    
    print("🏁 [모든 데이터 처리 완료]\n")
    return jsonify(response)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if IS_PROD:
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, 'index.html')
    return "Server is running."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)