import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


# =========================================================
# 1. 페이지 기본 설정
# =========================================================

st.set_page_config(
    page_title="나만의 영화 추천",
    page_icon="🎬",
    layout="wide",
)


# KOBIS 일일 박스오피스 API 주소
KOBIS_API_URL = (
    "https://www.kobis.or.kr/"
    "kobisopenapi/webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)


# =========================================================
# 2. 한국 시간 기준 '어제' 계산
# =========================================================

def get_yesterday_kst():
    """
    한국 시간 기준으로 어제 날짜를 계산합니다.

    서버가 미국이나 다른 나라에 있어도
    반드시 한국 시간(Asia/Seoul)을 기준으로 계산합니다.
    """

    # 한국 시간으로 현재 시각을 가져옵니다.
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))

    # 하루를 빼서 어제를 계산합니다.
    yesterday = now_kst - timedelta(days=1)

    # KOBIS가 요구하는 YYYYMMDD 형식으로 반환합니다.
    return yesterday.strftime("%Y%m%d")


# =========================================================
# 3. KOBIS API에서 박스오피스 가져오기
# =========================================================

@st.cache_data(ttl=60 * 30)
def get_kobis_movies(target_date):
    """
    KOBIS에서 지정 날짜의 일일 박스오피스를 가져옵니다.

    성공:
        (영화 목록, None)

    실패:
        (None, 오류 메시지)
    """

    # Streamlit Secrets에서 API 키를 가져옵니다.
    # 실제 키는 main.py에 절대 작성하지 않습니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]

    except (KeyError, FileNotFoundError):
        return None, (
            "KOBIS_KEY를 찾을 수 없습니다.\n\n"
            "Streamlit Cloud의 앱 설정 → Secrets에 "
            "KOBIS_KEY가 등록되어 있는지 확인해 주세요."
        )

    # KOBIS API에 전달할 값입니다.
    params = {
        "key": api_key,
        "targetDt": target_date,
    }

    try:
        # KOBIS API를 호출합니다.
        response = requests.get(
            KOBIS_API_URL,
            params=params,
            timeout=10,
        )

        # HTTP 오류가 있으면 예외를 발생시킵니다.
        response.raise_for_status()

        # JSON으로 변환합니다.
        data = response.json()

    except requests.exceptions.Timeout:
        return None, (
            "KOBIS API 요청 시간이 초과되었습니다.\n\n"
            "잠시 후 다시 시도해 주세요."
        )

    except requests.exceptions.RequestException as error:
        return None, (
            "KOBIS API에 연결하지 못했습니다.\n\n"
            f"오류 내용: {error}\n\n"
            "인터넷 연결 또는 KOBIS API 상태를 확인해 주세요."
        )

    except json.JSONDecodeError:
        return None, (
            "KOBIS API가 올바른 JSON 데이터를 보내지 않았습니다.\n\n"
            "KOBIS API 서비스 상태를 확인해 주세요."
        )

    # -----------------------------------------------------
    # KOBIS는 인증키가 잘못되어도 HTTP 200을 반환할 수 있습니다.
    #
    # 이 경우 boxOfficeResult 대신 faultInfo가 들어옵니다.
    # -----------------------------------------------------

    if "faultInfo" in data:

        fault_info = data.get("faultInfo", {})

        error_code = (
            fault_info.get("resultCode")
            or fault_info.get("faultCode")
            or "알 수 없음"
        )

        error_message = (
            fault_info.get("resultMsg")
            or fault_info.get("faultString")
            or "KOBIS API에서 오류가 발생했습니다."
        )

        return None, (
            "KOBIS API에서 오류를 반환했습니다.\n\n"
            f"- 오류 코드: {error_code}\n"
            f"- 오류 내용: {error_message}\n\n"
            "KOBIS_KEY가 정확한지 확인해 주세요."
        )

    # 정상적인 박스오피스 데이터를 가져옵니다.
    box_office_result = data.get("boxOfficeResult")

    if not box_office_result:
        return None, (
            "KOBIS 응답에 boxOfficeResult가 없습니다.\n\n"
            "KOBIS API 응답 형식 또는 서비스 상태를 확인해 주세요."
        )

    # 영화 목록을 가져옵니다.
    movies = box_office_result.get(
        "dailyBoxOfficeList",
        []
    )

    # API 호출은 성공했지만 영화 목록이 없는 경우입니다.
    if not movies:
        return None, (
            "KOBIS에서 영화 목록이 비어 있는 응답을 받았습니다.\n\n"
            "다음 내용을 확인해 주세요.\n"
            "• 조회 날짜의 데이터가 집계되었는지\n"
            "• KOBIS API가 정상적으로 작동하는지\n"
            "• 잠시 후 다시 시도해 보기"
        )

    return movies, None


# =========================================================
# 4. 숫자를 안전하게 변환하는 함수
# =========================================================

def to_number(value):
    """
    KOBIS에서 문자열로 전달되는 숫자를
    계산 가능한 숫자로 변환합니다.
    """

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


# =========================================================
# 5. 추천 점수 계산에 사용할 데이터 정규화
# =========================================================

def normalize_series(series):
    """
    서로 단위가 다른 데이터를 0~100점으로 변환합니다.

    예:
        관객수는 수만 명
        스크린수는 수백 개

    서로 직접 비교할 수 없기 때문에
    상대적인 점수로 바꿉니다.
    """

    minimum = series.min()
    maximum = series.max()

    # 모든 영화의 값이 같은 경우에는 모두 100점으로 처리합니다.
    if maximum == minimum:
        return pd.Series(
            [100.0] * len(series),
            index=series.index,
        )

    return (
        (series - minimum)
        / (maximum - minimum)
        * 100
    )


# =========================================================
# 6. 최신 영화 점수 계산
# =========================================================

def calculate_newness_score(open_dates, target_date):
    """
    개봉일이 최근일수록 높은 점수를 줍니다.

    KOBIS의 openDt를 이용합니다.
    """

    target = datetime.strptime(
        target_date,
        "%Y%m%d",
    ).date()

    scores = []

    for open_date in open_dates:

        try:
            release_date = datetime.strptime(
                str(open_date),
                "%Y-%m-%d",
            ).date()

            # 개봉 후 며칠이 지났는지 계산합니다.
            days = (target - release_date).days

            # 미래 개봉작처럼 이상한 날짜는 0점 처리합니다.
            if days < 0:
                days = 0

            # 최근 영화일수록 높은 점수를 받습니다.
            # 60일 이상 지난 영화는 0점에 가깝게 처리합니다.
            score = max(
                0,
                100 - (days / 60 * 100),
            )

        except (ValueError, TypeError):
            score = 0

        scores.append(score)

    return pd.Series(
        scores,
        index=open_dates.index,
    )


# =========================================================
# 7. 추천 점수 계산
# =========================================================

def calculate_recommendations(df, preferences, target_date):
    """
    사용자가 선택한 취향을 바탕으로
    각 영화의 추천 점수를 계산합니다.
    """

    result = df.copy()

    # -----------------------------------------------------
    # 각 지표를 0~100점으로 변환합니다.
    # -----------------------------------------------------

    result["관객수점수"] = normalize_series(
        result["audiCnt"]
    )

    result["누적관객점수"] = normalize_series(
        result["audiAcc"]
    )

    result["스크린점수"] = normalize_series(
        result["scrnCnt"]
    )

    result["상영량점수"] = normalize_series(
        result["showCnt"]
    )

    # 순위는 1위가 가장 높은 점수를 받도록 변환합니다.
    max_rank = result["rank"].max()

    if max_rank == 1:
        result["순위점수"] = 100
    else:
        result["순위점수"] = (
            (max_rank - result["rank"])
            / (max_rank - 1)
            * 100
        )

    # 최신성 점수를 계산합니다.
    result["최신성점수"] = calculate_newness_score(
        result["openDt"],
        target_date,
    )

    # -----------------------------------------------------
    # 사용자가 선택한 취향에 따라 가중치를 만듭니다.
    # -----------------------------------------------------

    weights = {
        "관객수": preferences["popular"],
        "누적관객": preferences["proven"],
        "최신성": preferences["new"],
        "스크린수": preferences["wide"],
        "상영량": preferences["many_show"],
        "순위": preferences["rank"],
    }

    # 가중치의 합이 100이 되도록 조정합니다.
    total_weight = sum(weights.values())

    if total_weight == 0:
        total_weight = 1

    # -----------------------------------------------------
    # 최종 추천 점수 계산
    # -----------------------------------------------------

    result["추천점수"] = (
        result["관객수점수"] * weights["관객수"]
        + result["누적관객점수"] * weights["누적관객"]
        + result["최신성점수"] * weights["최신성"]
        + result["스크린점수"] * weights["스크린수"]
        + result["상영량점수"] * weights["상영량"]
        + result["순위점수"] * weights["순위"]
    ) / total_weight

    # 높은 추천 점수부터 정렬합니다.
    result = result.sort_values(
        "추천점수",
        ascending=False,
    ).reset_index(drop=True)

    return result


# =========================================================
# 8. 추천 이유 만들기
# =========================================================

def make_reason(movie, preferences):
    """
    영화의 어떤 특징이 사용자의 취향과 잘 맞았는지
    간단한 설명을 만들어 줍니다.
    """

    reasons = []

    # 가장 중요하게 선택한 취향을 찾습니다.
    preference_names = {
        "popular": "현재 관객수가 많은 영화",
        "proven": "누적 관객수가 많은 검증된 영화",
        "new": "최근 개봉한 영화",
        "wide": "많은 스크린에서 상영되는 영화",
        "many_show": "상영 횟수가 많은 영화",
        "rank": "박스오피스 순위가 높은 영화",
    }

    sorted_preferences = sorted(
        preferences.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    # 가장 높은 가중치를 가진 취향 2개를 설명에 사용합니다.
    for key, weight in sorted_preferences[:2]:

        if weight > 0:
            reasons.append(
                preference_names[key]
            )

    if not reasons:
        return "현재 KOBIS 박스오피스 데이터를 기준으로 추천했습니다."

    if len(reasons) == 1:
        return f"{reasons[0]}를 선호하는 취향과 잘 맞습니다."

    return (
        f"{reasons[0]}이고 "
        f"{reasons[1]}인 영화를 선호하는 취향과 잘 맞습니다."
    )


# =========================================================
# 9. 화면 제목
# =========================================================

st.title("🎬 나만의 영화 추천")

st.write(
    "KOBIS의 최신 박스오피스 데이터를 바탕으로 "
    "당신의 취향에 맞는 영화를 찾아드립니다."
)

yesterday = get_yesterday_kst()

st.caption(
    f"한국 시간 기준 조회일: "
    f"{yesterday[:4]}년 {yesterday[4:6]}월 "
    f"{yesterday[6:]}일"
)


# =========================================================
# 10. KOBIS 데이터 가져오기
# =========================================================

with st.spinner(
    "KOBIS에서 최신 영화 데이터를 가져오는 중입니다..."
):

    movies, error_message = get_kobis_movies(
        yesterday
    )


# API 오류가 있으면 사용자가 확인할 내용을 보여줍니다.
if error_message:

    st.error(
        "영화 데이터를 가져오지 못했습니다."
    )

    st.warning(error_message)

    st.info(
        "확인해 볼 항목\n\n"
        "1. Streamlit Cloud의 Secrets에 KOBIS_KEY가 있는지\n"
        "2. KOBIS 인증키가 올바른지\n"
        "3. KOBIS API 사용이 정상적으로 가능한지\n"
        "4. 잠시 후 앱을 새로고침했는지"
    )

    st.stop()


# =========================================================
# 11. 데이터프레임 생성
# =========================================================

df = pd.DataFrame(movies)

# KOBIS의 숫자는 문자열로 오기 때문에 숫자로 변환합니다.
number_columns = [
    "rank",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt",
]

for column in number_columns:

    if column in df.columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        ).fillna(0)


# 필요한 컬럼이 없는 경우를 대비합니다.
required_columns = [
    "rank",
    "movieNm",
    "openDt",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt",
]

missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_columns:

    st.error(
        "KOBIS 응답에서 필요한 데이터가 일부 없습니다."
    )

    st.warning(
        "누락된 항목: "
        + ", ".join(missing_columns)
    )

    st.info(
        "KOBIS API 응답 형식이 변경되었는지 "
        "또는 KOBIS API 상태를 확인해 주세요."
    )

    st.stop()


if df.empty:

    st.warning(
        "영화 목록이 비어 있습니다."
    )

    st.info(
        "KOBIS의 해당 날짜 박스오피스 데이터가 "
        "정상적으로 집계되었는지 확인해 주세요."
    )

    st.stop()


# =========================================================
# 12. 사이드바 - 사용자 취향 입력
# =========================================================

st.sidebar.header("🎯 나의 영화 취향")

st.sidebar.write(
    "각 항목을 얼마나 중요하게 생각하는지 선택하세요."
)


popular = st.sidebar.slider(
    "🔥 현재 관객수가 많은 영화",
    min_value=0,
    max_value=5,
    value=4,
)

proven = st.sidebar.slider(
    "🏆 누적 관객수가 많은 영화",
    min_value=0,
    max_value=5,
    value=3,
)

new = st.sidebar.slider(
    "🆕 최신 개봉 영화",
    min_value=0,
    max_value=5,
    value=3,
)

wide = st.sidebar.slider(
    "🎞️ 많은 스크린에서 상영되는 영화",
    min_value=0,
    max_value=5,
    value=3,
)

many_show = st.sidebar.slider(
    "📽️ 상영 횟수가 많은 영화",
    min_value=0,
    max_value=5,
    value=2,
)

rank = st.sidebar.slider(
    "🥇 박스오피스 순위가 높은 영화",
    min_value=0,
    max_value=5,
    value=4,
)


# 사용자의 취향을 하나의 딕셔너리로 묶습니다.
preferences = {
    "popular": popular,
    "proven": proven,
    "new": new,
    "wide": wide,
    "many_show": many_show,
    "rank": rank,
}


# =========================================================
# 13. 추천 버튼
# =========================================================

st.sidebar.divider()

recommend_button = st.sidebar.button(
    "🎬 내 영화 추천받기",
    type="primary",
    use_container_width=True,
)


# 버튼을 누르지 않았다면 사용 방법을 보여줍니다.
if not recommend_button:

    st.subheader("👋 어떤 영화를 좋아하시나요?")

    st.write(
        "왼쪽에서 각 항목의 중요도를 조절한 뒤 "
        "**'내 영화 추천받기'** 버튼을 눌러주세요."
    )

    # 간단한 설명 카드
    col1, col2, col3 = st.columns(3)

    with col1:
        st.info(
            "🔥 인기 영화\n\n"
            "현재 관객수가 많은 영화를 선호한다면 "
            "관객수 중요도를 높여보세요."
        )

    with col2:
        st.info(
            "🆕 최신 영화\n\n"
            "새로 개봉한 영화를 좋아한다면 "
            "최신 개봉 중요도를 높여보세요."
        )

    with col3:
        st.info(
            "🏆 검증된 영화\n\n"
            "많은 사람이 본 영화를 선호한다면 "
            "누적 관객 중요도를 높여보세요."
        )

    st.divider()

    st.subheader("📊 현재 박스오피스")

    preview_df = df[
        [
            "rank",
            "movieNm",
            "audiCnt",
            "audiAcc",
            "scrnCnt",
        ]
    ].copy()

    preview_df.columns = [
        "순위",
        "영화명",
        "어제 관객수",
        "누적 관객수",
        "스크린수",
    ]

    st.dataframe(
        preview_df,
        use_container_width=True,
        hide_index=True,
    )

    st.stop()


# =========================================================
# 14. 추천 결과 계산
# =========================================================

recommendations = calculate_recommendations(
    df,
    preferences,
    yesterday,
)


# 추천 결과가 없는 경우를 방어합니다.
if recommendations.empty:

    st.warning(
        "추천할 영화가 없습니다."
    )

    st.info(
        "KOBIS 영화 데이터가 정상적으로 들어왔는지 "
        "확인해 주세요."
    )

    st.stop()


# =========================================================
# 15. 추천 결과 제목
# =========================================================

st.header("🍿 당신을 위한 영화 추천")

st.write(
    "선택한 취향을 KOBIS 박스오피스 지표에 반영하여 "
    "추천 점수를 계산했습니다."
)


# =========================================================
# 16. 1위 영화 크게 보여주기
# =========================================================

best_movie = recommendations.iloc[0]

st.subheader(
    f"🥇 오늘의 추천 영화 — {best_movie['movieNm']}"
)


# 추천 점수를 크게 보여줍니다.
score_col1, score_col2, score_col3 = st.columns(3)

with score_col1:

    st.metric(
        "추천 점수",
        f"{best_movie['추천점수']:.0f}점",
    )

with score_col2:

    st.metric(
        "KOBIS 순위",
        f"{int(best_movie['rank'])}위",
    )

with score_col3:

    st.metric(
        "어제 관객수",
        f"{int(best_movie['audiCnt']):,}명",
    )


# 추천 이유를 보여줍니다.
reason = make_reason(
    best_movie,
    preferences,
)

st.success(
    f"💡 추천 이유: {reason}"
)


# 1위 영화의 상세 정보
detail_col1, detail_col2, detail_col3 = st.columns(3)

with detail_col1:

    st.write("**개봉일**")

    st.write(
        best_movie["openDt"]
    )

with detail_col2:

    st.write("**누적 관객수**")

    st.write(
        f"{int(best_movie['audiAcc']):,}명"
    )

with detail_col3:

    st.write("**스크린수**")

    st.write(
        f"{int(best_movie['scrnCnt']):,}개"
    )


# =========================================================
# 17. 추천 TOP 5
# =========================================================

st.divider()

st.subheader("🏆 추천 TOP 5")


top5 = recommendations.head(5).copy()


for index, (_, movie) in enumerate(
    top5.iterrows(),
    start=1,
):

    # 영화별로 카드처럼 보이도록 컬럼을 사용합니다.
    col1, col2, col3 = st.columns(
        [1, 5, 2]
    )

    with col1:

        st.markdown(
            f"### {index}위"
        )

    with col2:

        st.markdown(
            f"**{movie['movieNm']}**"
        )

        st.caption(
            make_reason(
                movie,
                preferences,
            )
        )

    with col3:

        st.metric(
            "추천 점수",
            f"{movie['추천점수']:.0f}",
        )

    st.divider()


# =========================================================
# 18. 추천 TOP 5 비교 그래프
# =========================================================

st.subheader("📊 추천 영화 비교")

chart_df = top5[
    [
        "movieNm",
        "추천점수",
    ]
].copy()

chart_df = chart_df.set_index(
    "movieNm"
)

st.bar_chart(
    chart_df,
    y="추천점수",
    y_label="추천 점수",
)


# =========================================================
# 19. 전체 추천 결과 표
# =========================================================

st.subheader("🎞️ 전체 추천 결과")

result_table = recommendations[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt",
        "showCnt",
        "추천점수",
    ]
].copy()


# 표에 사용할 한국어 컬럼명을 지정합니다.
result_table.columns = [
    "KOBIS 순위",
    "영화명",
    "개봉일",
    "어제 관객수",
    "누적 관객수",
    "스크린수",
    "상영횟수",
    "추천점수",
]


# 숫자 형식을 보기 좋게 만듭니다.
for column in [
    "어제 관객수",
    "누적 관객수",
    "스크린수",
    "상영횟수",
]:

    result_table[column] = result_table[column].map(
        lambda value: f"{int(value):,}"
    )


result_table["추천점수"] = result_table[
    "추천점수"
].map(
    lambda value: f"{value:.0f}"
)


st.dataframe(
    result_table,
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# 20. 안내 문구
# =========================================================

st.caption(
    "※ 추천 점수는 KOBIS의 일일 박스오피스 데이터를 "
    "사용자 취향에 따라 가중하여 계산한 값입니다. "
    "장르·배우·감독 등의 정보는 사용하지 않습니다."
)

st.caption(
    f"※ 데이터 기준일: "
    f"{yesterday[:4]}-{yesterday[4:6]}-{yesterday[6:]}"
)

st.caption(
    "※ 데이터 출처: 영화관입장권통합전산망(KOBIS)"
)
