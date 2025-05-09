import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import re
from datetime import datetime, timedelta

# ----------------------------
# 앱 설정
# ----------------------------
st.set_page_config(
    page_title="Steam 게임 분석 (SteamSpy)",
    page_icon="🎮",
    layout="wide"
)

# 상단 스타일 및 헤더
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; color: #1e88e5; text-align: center; }
    .sub-header  { font-size: 1.5rem; color: #0d47a1; margin-top: 1rem; }
    .info-text   { font-size: 1rem; color: #424242; }
</style>
""", unsafe_allow_html=True)
st.markdown("<h1 class='main-header'>Steam 게임 장르별 분석 (SteamSpy)</h1>", unsafe_allow_html=True)
st.markdown("<p class='info-text'>SteamSpy API에서 실제 데이터를 가져와 소유자 수, 최근 2주간 플레이어 수, 평균 플레이타임을 분석합니다.</p>", unsafe_allow_html=True)

# ----------------------------
# SteamSpy API 호출 함수
# ----------------------------
@st.cache_data(ttl=3600)
def fetch_top_games():
    url = "https://steamspy.com/api.php?request=top100in2weeks"
    res = requests.get(url)
    return res.json() if res.status_code == 200 else {}

@st.cache_data(ttl=3600)
def fetch_game_details(appid):
    url = f"https://steamspy.com/api.php?request=appdetails&appid={appid}"
    res = requests.get(url)
    return res.json() if res.status_code == 200 else {}

# ----------------------------
# 사이드바 설정
# ----------------------------
with st.sidebar:
    st.header("설정")
    analysis_type = st.radio(
        "분석 항목", 
        ["소유자 수", "최근 2주간 플레이어 수", "평균 플레이타임"]
    )
    top_n = st.slider("상위 N개 게임", 5, 50, 10)

# ----------------------------
# 데이터 불러오기 및 전처리
# ----------------------------
with st.spinner("SteamSpy에서 데이터 불러오는 중..."):
    data = fetch_top_games()
if not data:
    st.error("SteamSpy 데이터를 불러올 수 없습니다.")
    st.stop()

# 진행률 표시 초기화
total = len(data)
progress_bar = st.progress(0)
rows = []
for idx, (appid, summary) in enumerate(data.items()):
    details = fetch_game_details(appid)
    # 장르 가져오기
    genre = details.get('genre', '').split(',')[0] if details.get('genre') else '알 수 없음'
    # 소유자 수
    owners_str = summary.get('owners', '').replace(',', '')
    nums = re.findall(r"\d+", owners_str)
    if len(nums) >= 2:
        low, high = map(int, nums[:2])
        owners = (low + high) // 2
    elif nums:
        owners = int(nums[0])
    else:
        owners = 0
    # 최근 2주간 플레이어 수
    raw_players = details.get('players_2weeks', details.get('average_2weeks', 0))
    try:
        players = int(raw_players)
    except:
        players = 0
    # 평균 플레이타임
    raw_avg = details.get('average_forever', 0)
    try:
        avg_time = int(raw_avg)
    except:
        avg_time = 0
    rows.append({
        '게임 ID': int(appid),
        '게임 이름': summary.get('name', '알 수 없음'),
        '장르': genre,
        '소유자 수': owners,
        '플레이어 수': players,
        '평균 플레이타임': avg_time
    })
    # 진행률 업데이트
    progress_bar.progress((idx + 1) / total)
# 진행률 제거
progress_bar.empty()

# DataFrame 생성
df = pd.DataFrame(rows)

# ----------------------------
# 상위 인기 게임 목록 & 차트
# ----------------------------
top_games = df.sort_values('플레이어 수', ascending=False).head(top_n)
st.subheader("🎮 상위 인기 게임 목록")
st.dataframe(top_games, use_container_width=True)
metric_map = {
    '소유자 수': '소유자 수',
    '최근 2주간 플레이어 수': '플레이어 수',
    '평균 플레이타임': '평균 플레이타임'
}
metric = metric_map.get(analysis_type, '플레이어 수')
fig = px.bar(
    top_games, x='게임 이름', y=metric, color='장르',
    labels={'게임 이름':'게임 이름', metric:analysis_type, '장르':'장르'},
    title=f"상위 {top_n}개 게임별 {analysis_type}"
)
fig.update_layout(xaxis_tickangle=-45, height=600)
st.plotly_chart(fig, use_container_width=True)

# ----------------------------
# 장르별 요약 분석
# ----------------------------
st.subheader("📊 장르별 요약 분석")
grouped = df.groupby('장르').agg({
    '소유자 수':'sum',
    '플레이어 수':'sum',
    '평균 플레이타임':'mean'
}).reset_index()
fig2 = px.bar(
    grouped.sort_values('플레이어 수', ascending=False),
    x='장르', y='플레이어 수', color='장르',
    labels={'플레이어 수':'플레이어 수', '장르':'장르'},
    title='장르별 최근 2주간 플레이어 수'
)
fig2.update_layout(height=500)
st.plotly_chart(fig2, use_container_width=True)

# ----------------------------
# 데이터 필터링 및 다운로드
# ----------------------------
st.subheader("🔍 데이터 필터링 및 다운로드")
col1, col2 = st.columns(2)
genres = df['장르'].dropna().unique().tolist()
with col1:
    sel_genres = st.multiselect('장르 선택', options=genres, default=genres)
with col2:
    min_time = st.slider('최소 평균 플레이타임(분)', 0, int(df['평균 플레이타임'].max()), 0)
filtered = df[(df['장르'].isin(sel_genres)) & (df['평균 플레이타임'] >= min_time)]
st.dataframe(filtered, use_container_width=True)
csv = filtered.to_csv(index=False).encode('utf-8-sig')
st.download_button('📥 CSV 다운로드', data=csv, file_name='steamspy_filtered.csv', mime='text/csv')

# ----------------------------
# 상세 정보 출력
# ----------------------------
st.subheader('📘 게임 상세 정보')
sel = st.selectbox('게임 선택', filtered['게임 이름'].unique().tolist())
selected = filtered[filtered['게임 이름'] == sel].iloc[0]
st.markdown(f"**장르**: {selected['장르']}")
st.markdown(f"**소유자 수**: {selected['소유자 수']}")
st.markdown(f"**최근 2주간 플레이어 수**: {selected['플레이어 수']}")
st.markdown(f"**평균 플레이타임**: {selected['평균 플레이타임']}분")
