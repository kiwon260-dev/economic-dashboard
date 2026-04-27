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

def safe_get(name, url, is_list=False):
    print(f"📡 [요청 시도] {name} 데이터...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        r = requests.get(url, timeout=10, verify=False, headers=headers)
        if r.status_code == 200:
            print(f"✅ [성공] {name}")
            return r.json()
    except Exception as e:
        print(f"🔥 [에러] {name}: {str(e)}")
    return [] if is_list else {"StatisticSearch": {"row": []}}

@app.route('/api/economic-data')
def get_economic_data():
    print("\n🚀 [API 호출 수신] 데이터 전송 준비")
    
    # 한국은행 데이터 호출
    base_rate = safe_get("금리", f"https://ecos.bok.or.kr/api/StatisticSearch/{BOK_KEY}/json/kr/1/10/722Y001/M/202301/202512/0101000")
    debt_data = safe_get("부채", f"https://ecos.bok.or.kr/api/StatisticSearch/{BOK_KEY}/json/kr/1/10/151Y005/Q/2023Q1/2025Q4")
    exchange = safe_get("환율", f"https://ecos.bok.or.kr/api/StatisticSearch/{BOK_KEY}/json/kr/1/10/731Y001/D/20240101/20251231/0000001")

    # 통계청 데이터 (차단되더라도 빈 배열 전송)
    unemp = safe_get("실업", f"https://kosis.kr/openapi/Param/statisticsParameterData.do?method=getList&apiKey={KOSIS_KEY}&itmId=T80+&objL1=ALL&objL2=00+&format=json&jsonVD=Y&prdSe=M&newEstPrdCnt=10&orgId=101&tblId=DT_1DA7102S", True)
    cpi = safe_get("물가", f"https://kosis.kr/openapi/Param/statisticsParameterData.do?method=getList&apiKey={KOSIS_KEY}&itmId=T&objL1=T10+&objL2=0+A+K&format=json&jsonVD=Y&prdSe=M&newEstPrdCnt=10&orgId=101&tblId=DT_1J22001", True)

    # 💡 [핵심] 리액트가 찾을 수 있는 모든 이름으로 다 넣어줍니다.
    response_data = {
        "bok_gdp": base_rate,       # 리액트가 bok_gdp를 찾으면 금리가 나옵니다.
        "bok_debt": debt_data,      # 부채
        "exchange_rate": exchange,  # 환율
        "base_rate": base_rate,     # 혹시 base_rate를 찾을까봐 한 번 더
        "unemp": unemp,
        "cpi": cpi
    }
    
    print("🏁 [반환] 데이터 조립 완료 (금리/부채/환율 포함)\n")
    return jsonify(response_data)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if IS_PROD:
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, 'index.html')
    return "Backend Running"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)