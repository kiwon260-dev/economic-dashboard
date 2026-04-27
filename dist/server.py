from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import requests, urllib3, os

# SSL 경고 무시 (일부 공공데이터 API 대응)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── 환경 설정 및 경로 확인 ──────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
dist_path = os.path.join(BASE_DIR, 'dist')
IS_PROD = os.path.isdir(dist_path)

print(f"\n{'='*50}")
print(f"[SYSTEM] 실행 경로: {BASE_DIR}")
print(f"[SYSTEM] 모드: {'PROD (dist 서빙)' if IS_PROD else 'DEV (API 전용)'}")
print(f"{'='*50}\n")

app = Flask(
    __name__,
    static_folder=dist_path if IS_PROD else None,
    static_url_path='' if IS_PROD else None,
)
CORS(app)

# API 키 설정
BOK_KEY   = "9PDUTTQC3QYSL870G1AX"
KOSIS_KEY = "NzllNGQwYjExYTI4ZWQ0NzhiZWNiNDAyYTAyNzNhODk="

def safe_get(name, url):
    print(f"📡 [요청 시도] {name} 데이터 호출 중...")
    
    # 💡 중요: 통계청(KOSIS) 등 서버 차단을 피하기 위해 브라우저인 척 헤더 추가
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01"
    }
    
    try:
        # timeout을 15초로 늘리고 headers 추가
        r = requests.get(url, timeout=15, verify=False, headers=headers)
        
        if r.status_code == 200:
            print(f"✅ [성공] {name} 데이터 수신 완료")
            return r.json()
        else:
            print(f"❌ [실패] {name} 응답 코드: {r.status_code}")
            return {"error": f"HTTP {r.status_code}", "detail": r.text[:100]}
            
    except Exception as e:
        print(f"🔥 [예외발생] {name}: {str(e)}")
        return {"error": str(e)}

@app.route('/api/economic-data')
def get_economic_data():
    print("\n🚀 [API 호출] /api/economic-data 요청 수신")
    
    data = {
        # 한국은행 (ECOS) - 금리/환율/부채
        "base_rate": safe_get("금리", f"https://ecos.bok.or.kr/api/StatisticSearch/{BOK_KEY}/json/kr/1/10/722Y001/M/202301/202512/0101000"),
        "exchange_rate": safe_get("환율", f"https://ecos.bok.or.kr/api/StatisticSearch/{BOK_KEY}/json/kr/1/10/731Y001/D/20240101/20251231/0000001"),
        "bok_debt": safe_get("부채", f"https://ecos.bok.or.kr/api/StatisticSearch/{BOK_KEY}/json/kr/1/10/151Y005/Q/2023Q1/2025Q4"),
        
        # 통계청 (KOSIS) - 실업/물가 (헤더 추가로 차단 해결 시도)
        "unemp": safe_get("실업", f"https://kosis.kr/openapi/Param/statisticsParameterData.do?method=getList&apiKey={KOSIS_KEY}&itmId=T80+&objL1=ALL&objL2=00+&format=json&jsonVD=Y&prdSe=M&newEstPrdCnt=10&orgId=101&tblId=DT_1DA7102S"),
        "cpi": safe_get("물가", f"https://kosis.kr/openapi/Param/statisticsParameterData.do?method=getList&apiKey={KOSIS_KEY}&itmId=T&objL1=T10+&objL2=0+A+K&format=json&jsonVD=Y&prdSe=M&newEstPrdCnt=10&orgId=101&tblId=DT_1J22001"),
    }
    
    print("🏁 [요청 종료] 모든 API 응답 처리 완료\n")
    return jsonify(data)

# ── 정적 파일 서빙 (React 빌드 결과물) ──────────────────────────────────
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if IS_PROD:
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, 'index.html')
    else:
        return "Backend is running. (dist folder not found - check build)"

if __name__ == "__main__":
    # Render 환경에 맞게 포트 설정
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)