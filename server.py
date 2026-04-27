from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import requests, urllib3, os, sys

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── 환경 자동 감지 및 경로 확인 로그 ──────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
dist_path = os.path.join(BASE_DIR, 'dist')
IS_PROD = os.path.isdir(dist_path)

print(f"\n{'='*50}")
print(f"[SYSTEM] 현재 실행 경로: {BASE_DIR}")
print(f"[SYSTEM] dist 폴더 존재 여부: {IS_PROD}")
print(f"[SYSTEM] 실행 모드: {'PROD (dist 서빙)' if IS_PROD else 'DEV (API 전용)'}")
print(f"{'='*50}\n")

app = Flask(
    __name__,
    static_folder=dist_path if IS_PROD else None,
    static_url_path='' if IS_PROD else None,
)
CORS(app)

BOK_KEY   = "9PDUTTQC3QYSL870G1AX"
KOSIS_KEY = "NzllNGQwYjExYTI4ZWQ0NzhiZWNiNDAyYTAyNzNhODk="

def safe_get(name, url):
    print(f"📡 [요청 시도] {name} 데이터...")
    try:
        r = requests.get(url, timeout=10, verify=False)
        if r.status_code == 200:
            data = r.json()
            # 데이터 구조가 비어있는지 확인
            if not data or (isinstance(data, dict) and not data):
                 print(f"⚠️  [경고] {name}: 연결은 성공했으나 응답 데이터가 비어있음.")
            else:
                 print(f"✅ [성공] {name} 데이터 수신 완료 (Status: {r.status_code})")
            return data
        else:
            print(f"❌ [실패] {name}: 서버 응답 에러 (Status: {r.status_code})")
            return {"error": f"Status {r.status_code}"}
    except requests.exceptions.Timeout:
        print(f"⏰ [타임아웃] {name}: API 서버 응답 시간이 초과되었습니다.")
        return {"error": "timeout"}
    except Exception as e:
        print(f"❗ [예외발생] {name}: {str(e)}")
        # 무료 계정 차단 확인용 로그
        if "Connection refused" in str(e) or "Max retries exceeded" in str(e):
            print(f"    👉 [진단] PythonAnywhere 무료 계정의 외부 사이트 차단일 가능성이 큼.")
        return {"error": str(e)}

@app.route('/api/economic-data')
def get_data():
    print(f"\n🚀 [API 호출] /api/economic-data 요청 수신")
    
    response_data = {
        "bok_rate": safe_get("금리", (
            f"https://ecos.bok.or.kr/api/StatisticSearch/{BOK_KEY}"
            f"/json/kr/1/10/722Y001/D/20240101/20260430/0101000"
        )),
        "bok_exch": safe_get("환율", (
            f"https://ecos.bok.or.kr/api/StatisticSearch/{BOK_KEY}"
            f"/json/kr/1/10/731Y003/D/20240101/20260430/0000003"
        )),
        "bok_debt": safe_get("부채", (
            f"https://ecos.bok.or.kr/api/StatisticSearch/{BOK_KEY}"
            f"/json/kr/1/10/151Y005/Q/2023Q1/2025Q4"
        )),
        "unemp": safe_get("실업", (
            f"https://kosis.kr/openapi/Param/statisticsParameterData.do"
            f"?method=getList&apiKey={KOSIS_KEY}&itmId=T80+&objL1=ALL&objL2=00+"
            f"&format=json&jsonVD=Y&prdSe=M&newEstPrdCnt=10&orgId=101&tblId=DT_1DA7102S"
        )),
        "cpi": safe_get("물가", (
            f"https://kosis.kr/openapi/Param/statisticsParameterData.do"
            f"?method=getList&apiKey={KOSIS_KEY}&itmId=T&objL1=T10+&objL2=0+A+K"
            f"&format=json&jsonVD=Y&prdSe=M&newEstPrdCnt=10&orgId=101&tblId=DT_1J22001"
        )),
    }
    
    print(f"🏁 [요청 종료] 모든 API 응답 처리 완료\n")
    return jsonify(response_data)

# ── 프로덕션 전용: React 빌드 파일 서빙 ──────────────────────────────────
if IS_PROD:
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        full_path = os.path.join(app.static_folder, path)
        if path != "" and os.path.exists(full_path):
            return send_from_directory(app.static_folder, path)
        else:
            print(f"🏠 [정적파일] {path or 'index.html'} 서빙 중...")
            return send_from_directory(app.static_folder, 'index.html')

application = app

if __name__ == '__main__':
    # 로컬 실행 시
    print(f"\n[*] 로컬 서버를 시작합니다: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)