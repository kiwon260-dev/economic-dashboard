from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import requests, urllib3, os

# SSL 경고 무시
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

# API 키
BOK_KEY   = "9PDUTTQC3QYSL870G1AX"
KOSIS_KEY = "NzllNGQwYjExYTI4ZWQ0NzhiZWNiNDAyYTAyNzNhODk="

def safe_get(name, url):
    print(f"📡 [요청 시도] {name} 데이터...")
    
    # 통계청 차단 방지를 위한 브라우저 위장 헤더
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://kosis.kr/"
    }
    
    try:
        # 하나가 죽어도 전체가 안 멈추게 timeout 설정 및 예외처리 강화
        r = requests.get(url, timeout=12, verify=False, headers=headers)
        
        if r.status_code == 200:
            print(f"✅ [성공] {name} 데이터 수신")
            return r.json()
        else:
            print(f"❌ [실패] {name} 응답코드: {r.status_code}")
            return {"error": f"HTTP {r.status_code}"}
            
    except Exception as e:
        print(f"🔥 [예외발생] {name}: {str(e)}")
        return {"error": "Connection Failed"}

@app.route('/api/economic-data')
def get_economic_data():
    print("\n🚀 [API 호출 수신]")
    
    # 한국은행 데이터 (아까 잘 나오던 것들)
    base_rate = safe_get("금리", f"https://ecos.bok.or.kr/api/StatisticSearch/{BOK_KEY}/json/kr/1/10/722Y001/M/202301/202512/0101000")
    exchange_rate = safe_get("환율", f"https://ecos.bok.or.kr/api/StatisticSearch/{BOK_KEY}/json/kr/1/10/731Y001/D/20240101/20251231/0000001")
    bok_debt = safe_get("부채", f"https://ecos.bok.or.kr/api/StatisticSearch/{BOK_KEY}/json/kr/1/10/151Y005/Q/2023Q1/2025Q4")
    
    # 통계청 데이터 (차단 위험이 있는 것들)
    unemp = safe_get("실업", f"https://kosis.kr/openapi/Param/statisticsParameterData.do?method=getList&apiKey={KOSIS_KEY}&itmId=T80+&objL1=ALL&objL2=00+&format=json&jsonVD=Y&prdSe=M&newEstPrdCnt=10&orgId=101&tblId=DT_1DA7102S")
    cpi = safe_get("물가", f"https://kosis.kr/openapi/Param/statisticsParameterData.do?method=getList&apiKey={KOSIS_KEY}&itmId=T&objL1=T10+&objL2=0+A+K&format=json&jsonVD=Y&prdSe=M&newEstPrdCnt=10&orgId=101&tblId=DT_1J22001")

    # 최종 결과 조립
    data = {
        "base_rate": base_rate,
        "exchange_rate": exchange_rate,
        "bok_debt": bok_debt,
        "unemp": unemp,
        "cpi": cpi
    }
    
    print("🏁 [모든 데이터 처리 완료]\n")
    return jsonify(data)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if IS_PROD:
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, 'index.html')
    return "Server is running. Please check your dist folder."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)