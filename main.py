import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


# ============================================================
# 🎬 영화 흥행 탐정
# KOBIS API만 사용하는 Streamlit 웹앱
# ============================================================


# ------------------------------------------------------------
# 페이지 설정
# ------------------------------------------------------------

st.set_page_config(
    page_title="영화 흥행 탐정",
    page_icon="🕵️",
    layout="wide",
)


# ============================================================
# 🎨 앱 디자인
# ============================================================

st.markdown(
    """
    <style>

    /* 전체 배경 */
    .stApp {
        background:
            radial-gradient(
                circle at top right,
                #25213f 0%,
                #11111c 38%,
                #09090f 100%
            );
        color: #f5f5f7;
    }

    /* 기본 글자 */
    html, body, [class*="css"] {
        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            sans-serif;
    }

    /* 메인 제목 */
    .main-title {
        font-size: 3.4rem;
        font-weight: 900;
        letter-spacing: -2px;
        margin-bottom: 0.2rem;
        color: white;
    }

    .subtitle {
        font-size: 1.15rem;
        color: #aaaabd;
        margin-bottom: 2rem;
    }

    /* 탐정 말풍선 */
    .detective-bubble {
        position: relative;
        background:
            linear-gradient(
                135deg,
                #29224d,
                #17152d
            );
        border: 2px solid #8b6cff;
        border-radius: 28px;
        padding: 30px 35px;
        margin: 20px 0 35px 0;
        box-shadow:
            0 15px 45px rgba(112, 82, 255, 0.20),
            inset 0 1px 0 rgba(255,255,255,0.08);
    }

    /* 말풍선 꼬리 */
    .detective-bubble:after {
        content: "";
        position: absolute;
        bottom: -18px;
        left: 70px;
        width: 32px;
        height: 32px;
        background: #1b1834;
        border-right: 2px solid #8b6cff;
        border-bottom: 2px solid #8b6cff;
        transform: rotate(45deg);
    }

    .detective-label {
        font-size: 1rem;
        font-weight: 800;
        color: #a995ff;
        margin-bottom: 10px;
        letter-spacing: 0.5px;
    }

    .detective-text {
        font-size: 1.55rem;
        line-height: 1.65;
        font-weight: 700;
        color: #ffffff;
        letter-spacing: -0.5px;
    }

    .detective-text strong {
        color: #c4b7ff;
    }

    /* 작은 탐정 코멘트 */
    .small-bubble {
        background: #171624;
        border: 1px solid #3d3856;
        border-radius: 18px;
        padding: 18px 22px;
        margin: 14px 0 28px 0;
        color: #e7e5f2;
        font-size: 1.05rem;
        line-height: 1.65;
    }

    /* 섹션 제목 */
    .section-title {
        font-size: 1.7rem;
        font-weight: 850;
        color: white;
        margin-top: 25px;
        margin-bottom: 8px;
    }

    /* 카드 */
    .stat-card {
        background:
            linear-gradient(
                145deg,
                #191827,
                #12121d
            );
        border: 1px solid #302c43;
        border-radius: 22px;
        padding: 24px;
        min-height: 145px;
        box-shadow:
            0 10px 30px rgba(0,0,0,0.22);
    }

    .stat-label {
        color: #9995aa;
        font-size: 0.95rem;
        margin-bottom: 10px;
    }

    .stat-value {
        color: white;
        font-size: 2rem;
        font-weight: 850;
    }

    /* 영화 제목 카드 */
    .movie-header {
        background:
            linear-gradient(
                120deg,
                #211c3c,
                #151421
            );
        border-radius: 26px;
        padding: 28px 32px;
        border: 1px solid #37314f;
        margin: 20px 0;
    }

    .movie-name {
        font-size: 2.2rem;
        font-weight: 900;
        color: white;
    }

    .movie-info {
        color: #aaa7b8;
        font-size: 1rem;
        margin-top: 8px;
    }

    /* 안내 박스 */
    .info-box {
        background: #151525;
        border: 1px solid #393452;
        border-radius: 16px;
        padding: 18px 22px;
        color: #d8d5e3;
        line-height: 1.7;
    }

    /* 구분선 */
    hr {
        border-color: #2b2839 !important;
    }

    /* Streamlit selectbox */
    div[data-baseweb="select"] > div {
        background-color: #181725;
        border-color: #3b3651;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 🔑 KOBIS API 설정
# ============================================================

KOBIS_URL = (
    "https://www.kobis.or.kr/"
    "kobisopenapi/webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)


# ============================================================
# 🇰🇷 한국 시간
# ============================================================

def get_korea_today():
    """
    서버가 어느 나라에 있든
    한국 시간 기준 오늘 날짜를 가져옵니다.
    """

    return datetime.now(
        ZoneInfo("Asia/Seoul")
    ).date()


def get_yesterday():
    """한국 시간 기준 어제를 계산합니다."""

    return (
        get_korea_today()
        - timedelta(days=1)
    )


def to_kobis_date(date_value):
    """날짜를 KOBIS용 YYYYMMDD로 바꿉니다."""

    return date_value.strftime(
        "%Y%m%d"
    )


def pretty_date(date_value):
    """날짜를 한국어로 표시합니다."""

    return date_value.strftime(
        "%Y년 %m월 %d일"
    )


# ============================================================
# 🔢 숫자 처리
# ============================================================

def safe_int(value):
    """
    KOBIS에서는 숫자도 문자열로 옵니다.
    안전하게 정수로 변환합니다.
    """

    try:
        return int(value)

    except (ValueError, TypeError):
        return 0


def comma(value):
    """천 단위 쉼표를 붙입니다."""

    return f"{int(value):,}"


def change_rate(first, last):
    """두 숫자의 변화율을 계산합니다."""

    if first == 0:
        return None

    return (
        (last - first)
        / first
        * 100
    )


# ============================================================
# 🎬 KOBIS 일일 박스오피스 조회
# ============================================================

@st.cache_data(ttl=1800)
def get_boxoffice(target_date):
    """
    KOBIS에서 특정 날짜의 박스오피스를 가져옵니다.
    """

    # Secrets에서 API 키를 가져옵니다.
    try:

        api_key = st.secrets[
            "KOBIS_KEY"
        ]

    except (KeyError, FileNotFoundError):

        return None, (
            "KOBIS_KEY가 없습니다."
        )

    params = {
        "key": api_key,
        "targetDt": target_date,
    }

    try:

        response = requests.get(
            KOBIS_URL,
            params=params,
            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

    except requests.exceptions.Timeout:

        return None, (
            "KOBIS API 요청 시간이 초과되었습니다."
        )

    except requests.exceptions.RequestException as error:

        return None, (
            f"KOBIS API 연결에 실패했습니다.\n\n"
            f"{error}"
        )

    except json.JSONDecodeError:

        return None, (
            "KOBIS에서 올바른 JSON 데이터를 "
            "받지 못했습니다."
        )

    # --------------------------------------------------------
    # 중요:
    # KOBIS는 인증키가 잘못되어도 HTTP 200을 줄 수 있습니다.
    # 따라서 faultInfo를 확인합니다.
    # --------------------------------------------------------

    if "faultInfo" in data:

        fault = data["faultInfo"]

        code = (
            fault.get("resultCode")
            or fault.get("faultCode")
            or "알 수 없음"
        )

        message = (
            fault.get("resultMsg")
            or fault.get("faultString")
            or "알 수 없는 오류"
        )

        return None, (
            f"KOBIS API 오류\n\n"
            f"오류 코드: {code}\n"
            f"오류 내용: {message}"
        )

    result = data.get(
        "boxOfficeResult"
    )

    if not result:

        return None, (
            "boxOfficeResult가 없습니다."
        )

    movies = result.get(
        "dailyBoxOfficeList",
        [],
    )

    if not movies:

        return None, (
            "영화 목록이 비어 있습니다."
        )

    return movies, None


# ============================================================
# 🕵️ 특정 영화의 최근 기록
# ============================================================

@st.cache_data(ttl=1800)
def get_movie_history(
    movie_name,
    end_date_string,
    days=14,
):
    """
    선택한 영화의 최근 14일 데이터를 가져옵니다.
    """

    end_date = datetime.strptime(
        end_date_string,
        "%Y-%m-%d",
    ).date()

    records = []

    failed_dates = []

    for i in range(days):

        target_date = (
            end_date
            - timedelta(days=i)
        )

        movies, error = get_boxoffice(
            to_kobis_date(target_date)
        )

        if error:

            failed_dates.append(
                target_date
            )

            continue

        found = None

        for movie in movies:

            if (
                movie.get("movieNm")
                == movie_name
            ):

                found = movie
                break

        if found is None:
            continue

        records.append(
            {
                "날짜": target_date,

                "순위": safe_int(
                    found.get("rank")
                ),

                "영화명": found.get(
                    "movieNm",
                    movie_name,
                ),

                "개봉일": found.get(
                    "openDt",
                    "",
                ),

                "관객수": safe_int(
                    found.get("audiCnt")
                ),

                "누적관객": safe_int(
                    found.get("audiAcc")
                ),

                "스크린수": safe_int(
                    found.get("scrnCnt")
                ),

                "상영횟수": safe_int(
                    found.get("showCnt")
                ),
            }
        )

    records.sort(
        key=lambda x: x["날짜"]
    )

    return records, failed_dates


# ============================================================
# 🗣️ 탐정 멘트 만들기
# ============================================================

def audience_story(history):

    if len(history) < 2:

        return (
            "아직 비교할 데이터가 충분하지 않아요. "
            "조금 더 기록이 쌓이면 관객 흐름을 확인할 수 있습니다."
        )

    first = history[0]["관객수"]
    last = history[-1]["관객수"]

    rate = change_rate(
        first,
        last,
    )

    if rate is None:

        return (
            "관객수 변화를 계산하기 어렵습니다."
        )

    if rate >= 50:

        return (
            f"🔥 최근 비교 기간에 관객수가 "
            f"**{rate:.1f}% 증가**했습니다! "
            "관객 유입이 크게 늘어난 구간입니다."
        )

    if rate >= 20:

        return (
            f"📈 관객수가 **{rate:.1f}% 증가**했습니다. "
            "최근 관객 흐름이 꽤 활발해졌습니다."
        )

    if rate >= 5:

        return (
            f"🙂 관객수가 **{rate:.1f}% 증가**했습니다. "
            "완만하지만 증가하는 흐름입니다."
        )

    if rate > -5:

        return (
            "😐 관객수가 크게 움직이지 않았습니다. "
            "최근 관객 흐름이 비교적 안정적입니다."
        )

    if rate > -20:

        return (
            f"📉 관객수가 **{abs(rate):.1f}% 감소**했습니다. "
            "최근 관객 유입이 조금씩 줄어드는 모습입니다."
        )

    if rate > -50:

        return (
            f"🍂 관객수가 **{abs(rate):.1f}% 감소**했습니다. "
            "초반에 비해 관객 흐름이 약해진 모습입니다."
        )

    return (
        f"🌙 관객수가 **{abs(rate):.1f}% 감소**했습니다. "
        "최근 관객 유입이 크게 줄어든 상태입니다."
    )


def rank_story(history):

    if len(history) < 2:

        return (
            "순위 변화를 비교할 데이터가 부족합니다."
        )

    first = history[0]["순위"]
    last = history[-1]["순위"]

    difference = first - last

    if difference >= 5:

        return (
            f"🚀 순위가 **{difference}계단 상승**했습니다! "
            "최근 기록에서 순위 변화가 상당히 크게 나타났습니다."
        )

    if difference > 0:

        return (
            f"📈 순위가 **{difference}계단 상승**했습니다."
        )

    if difference <= -5:

        return (
            f"📉 순위가 **{abs(difference)}계단 하락**했습니다."
        )

    if difference < 0:

        return (
            f"📉 순위가 **{abs(difference)}계단 하락**했습니다."
        )

    return (
        "🧘 순위가 그대로입니다. "
        "최근 비교 기간 동안 큰 변화가 없었습니다."
    )


def screen_story(history):

    if len(history) < 2:

        return (
            "스크린수 변화를 비교할 데이터가 부족합니다."
        )

    first = history[0]["스크린수"]
    last = history[-1]["스크린수"]

    difference = last - first

    if difference >= 100:

        return (
            f"🎞️ 스크린이 **{difference:,}개 증가**했습니다! "
            "극장 편성이 크게 확대된 구간입니다."
        )

    if difference > 0:

        return (
            f"🎞️ 스크린이 **{difference:,}개 증가**했습니다."
        )

    if difference <= -100:

        return (
            f"🎞️ 스크린이 **{abs(difference):,}개 감소**했습니다. "
            "극장 편성이 상당히 축소된 흐름입니다."
        )

    if difference < 0:

        return (
            f"🎞️ 스크린이 **{abs(difference):,}개 감소**했습니다."
        )

    return (
        "🎞️ 스크린수가 거의 그대로입니다. "
        "극장 편성이 비교적 안정적으로 유지되고 있습니다."
    )


def show_story(history):

    if len(history) < 2:

        return (
            "상영횟수 변화를 비교할 데이터가 부족합니다."
        )

    first = history[0]["상영횟수"]
    last = history[-1]["상영횟수"]

    difference = last - first

    if difference > 100:

        return (
            f"📽️ 하루 상영횟수가 **{difference:,}회 증가**했습니다! "
            "상영 편성이 크게 확대된 구간입니다."
        )

    if difference > 0:

        return (
            f"📽️ 상영횟수가 **{difference:,}회 증가**했습니다."
        )

    if difference < -100:

        return (
            f"📽️ 상영횟수가 **{abs(difference):,}회 감소**했습니다. "
            "상영 편성이 눈에 띄게 줄었습니다."
        )

    if difference < 0:

        return (
            f"📽️ 상영횟수가 **{abs(difference):,}회 감소**했습니다."
        )

    return (
        "📽️ 상영횟수에는 큰 변화가 없습니다."
    )


# ============================================================
# 🕵️ 메인 탐정 코멘트
# ============================================================

def detective_summary(history):

    if len(history) < 2:

        return (
            "아직 사건 파일이 얇습니다. "
            "조금 더 데이터가 쌓이면 영화의 흐름을 살펴볼 수 있어요."
        )

    first = history[0]
    last = history[-1]

    audience_rate = change_rate(
        first["관객수"],
        last["관객수"],
    )

    screen_difference = (
        last["스크린수"]
        - first["스크린수"]
    )

    rank_difference = (
        first["순위"]
        - last["순위"]
    )

    # 관객 증가 + 스크린 증가
    if (
        audience_rate is not None
        and audience_rate > 10
        and screen_difference > 0
    ):

        return (
            "🎬 흥미로운 장면입니다. "
            f"최근 비교 기간 동안 관객수가 **{audience_rate:.1f}% 증가**했고 "
            f"스크린도 **{screen_difference:,}개 증가**했습니다. "
            "두 지표가 같은 방향으로 움직였네요."
        )

    # 관객 증가 + 스크린 감소
    if (
        audience_rate is not None
        and audience_rate > 10
        and screen_difference < 0
    ):

        return (
            "🕵️ 오, 여기서 반전이 보입니다. "
            f"스크린은 **{abs(screen_difference):,}개 줄었는데** "
            f"관객수는 **{audience_rate:.1f}% 증가**했습니다. "
            "최근 기록에서는 두 지표가 서로 다른 방향으로 움직였습니다."
        )

    # 관객 감소 + 스크린 증가
    if (
        audience_rate is not None
        and audience_rate < -10
        and screen_difference > 0
    ):

        return (
            "🔍 흥미로운 기록이 잡혔습니다. "
            f"스크린은 **{screen_difference:,}개 늘었지만** "
            f"관객수는 **{abs(audience_rate):.1f}% 감소**했습니다. "
            "상영관 편성과 관객 흐름이 같은 방향으로 움직이지 않았습니다."
        )

    # 순위 상승
    if rank_difference >= 3:

        return (
            "🚀 순위 변화가 눈에 띕니다. "
            f"최근 비교 기간 동안 **{rank_difference}계단 상승**했습니다. "
            "박스오피스 순위에서 움직임이 확인됩니다."
        )

    # 순위 하락
    if rank_difference <= -3:

        return (
            "📉 순위 쪽에서 변화가 포착됐습니다. "
            f"최근 비교 기간 동안 **{abs(rank_difference)}계단 하락**했습니다."
        )

    # 기본 멘트
    return (
        "🕵️ 현재 사건 파일을 종합해보면, "
        "관객수·스크린수·순위가 각각 어떻게 움직였는지를 "
        "함께 살펴보는 것이 핵심입니다."
    )


# ============================================================
# 🏠 앱 시작
# ============================================================

st.markdown(
    '<div class="main-title">🕵️ 영화 흥행 탐정</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    'KOBIS 데이터를 뒤져 영화의 흥행 흐름을 추적합니다.'
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# 📅 어제 날짜
# ============================================================

yesterday = get_yesterday()

st.caption(
    f"📅 조사 기준일: {pretty_date(yesterday)} · 한국 시간 기준"
)


# ============================================================
# 📡 KOBIS 데이터 조회
# ============================================================

with st.spinner(
    "🕵️ 사건 현장의 데이터를 가져오는 중..."
):

    movies, error = get_boxoffice(
        to_kobis_date(yesterday)
    )


# ============================================================
# 🚨 API 오류 처리
# ============================================================

if error:

    st.error(
        "🚨 사건 파일을 열 수 없습니다."
    )

    st.warning(error)

    st.markdown(
        """
        <div class="info-box">

        ### 🔧 탐정의 체크리스트

        1. Streamlit Cloud의 **Settings → Secrets**를 확인하세요.
        2. `KOBIS_KEY`라는 이름으로 인증키가 저장되어 있는지 확인하세요.
        3. 인증키에 오타나 불필요한 공백이 없는지 확인하세요.
        4. KOBIS API가 일시적으로 응답하지 않는지 확인하세요.
        5. 잠시 후 페이지를 새로고침해 보세요.

        </div>
        """,
        unsafe_allow_html=True,
    )

    st.stop()


# ============================================================
# 🎬 영화 목록 확인
# ============================================================

movie_names = [
    movie.get("movieNm")
    for movie in movies
    if movie.get("movieNm")
]


if not movie_names:

    st.warning(
        "🎬 오늘 조사할 영화 목록이 없습니다."
    )

    st.info(
        "한국 시간 기준 어제의 KOBIS 박스오피스 "
        "데이터가 정상적으로 집계되었는지 확인해 주세요."
    )

    st.stop()


# ============================================================
# 🔎 영화 선택
# ============================================================

st.markdown(
    '<div class="section-title">🔎 영화 선택</div>',
    unsafe_allow_html=True,
)

selected_movie = st.selectbox(
    "어떤 영화를 조사할까요?",
    movie_names,
    label_visibility="collapsed",
)


# ============================================================
# 🎬 선택 영화 정보 찾기
# ============================================================

latest = None

for movie in movies:

    if movie.get("movieNm") == selected_movie:

        latest = movie
        break


if latest is None:

    st.warning(
        "선택한 영화의 데이터를 찾지 못했습니다."
    )

    st.stop()


# ============================================================
# 🔢 현재 수치
# ============================================================

current_rank = safe_int(
    latest.get("rank")
)

current_audience = safe_int(
    latest.get("audiCnt")
)

current_acc = safe_int(
    latest.get("audiAcc")
)

current_screens = safe_int(
    latest.get("scrnCnt")
)

current_shows = safe_int(
    latest.get("showCnt")
)

release_date = latest.get(
    "openDt",
    "",
)


# ============================================================
# 🎬 영화 헤더
# ============================================================

st.markdown(
    f"""
    <div class="movie-header">

        <div class="movie-name">
            🎬 {selected_movie}
        </div>

        <div class="movie-info">
            개봉일: {release_date or "정보 없음"}
            &nbsp;&nbsp;|&nbsp;&nbsp;
            기준일: {pretty_date(yesterday)}
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 🗂️ 최근 14일 데이터
# ============================================================

with st.spinner(
    "📂 과거 사건 기록을 뒤지는 중..."
):

    history, failed_dates = get_movie_history(
        selected_movie,
        yesterday.isoformat(),
        days=14,
    )


if not history:

    st.warning(
        "🗂️ 이 영화의 최근 기록을 찾지 못했습니다."
    )

    st.info(
        """
        다음 사항을 확인해 주세요.

        - 영화가 최근 박스오피스에 포함되어 있었는지
        - 영화가 개봉한 지 얼마 되지 않았는지
        - KOBIS에서 해당 날짜의 데이터가 제공되는지
        """
    )

    st.stop()


# ============================================================
# 🕵️🔥 가장 중요한 탐정 말풍선
# ============================================================

main_comment = detective_summary(
    history
)

st.markdown(
    f"""
    <div class="detective-bubble">

        <div class="detective-label">
            🕵️ 탐정의 현장 브리핑
        </div>

        <div class="detective-text">
            {main_comment}
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 📊 핵심 지표
# ============================================================

st.markdown(
    '<div class="section-title">📊 현재 사건 기록</div>',
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)

with col1:

    st.markdown(
        f"""
        <div class="stat-card">

            <div class="stat-label">
                🏆 어제 순위
            </div>

            <div class="stat-value">
                {current_rank}위
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with col2:

    st.markdown(
        f"""
        <div class="stat-card">

            <div class="stat-label">
                👥 어제 관객수
            </div>

            <div class="stat-value">
                {comma(current_audience)}명
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with col3:

    st.markdown(
        f"""
        <div class="stat-card">

            <div class="stat-label">
                🎟️ 누적 관객
            </div>

            <div class="stat-value">
                {comma(current_acc)}명
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


st.write("")

col4, col5 = st.columns(2)

with col4:

    st.markdown(
        f"""
        <div class="stat-card">

            <div class="stat-label">
                🎞️ 스크린수
            </div>

            <div class="stat-value">
                {comma(current_screens)}개
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with col5:

    st.markdown(
        f"""
        <div class="stat-card">

            <div class="stat-label">
                📽️ 상영횟수
            </div>

            <div class="stat-value">
                {comma(current_shows)}회
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# 👥 관객수
# ============================================================

st.divider()

st.markdown(
    '<div class="section-title">'
    '👥 관객수 추적'
    '</div>',
    unsafe_allow_html=True,
)

audience_df = pd.DataFrame(
    {
        "일일 관객수": [
            item["관객수"]
            for item in history
        ]
    },
    index=[
        item["날짜"].strftime("%m/%d")
        for item in history
    ],
)

st.line_chart(
    audience_df
)

st.markdown(
    f"""
    <div class="small-bubble">
        🕵️ <b>탐정:</b>
        {audience_story(history)}
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 🏆 순위
# ============================================================

st.markdown(
    '<div class="section-title">'
    '🏆 순위 추적'
    '</div>',
    unsafe_allow_html=True,
)

rank_df = pd.DataFrame(
    {
        "순위": [
            item["순위"]
            for item in history
        ]
    },
    index=[
        item["날짜"].strftime("%m/%d")
        for item in history
    ],
)

# 숫자가 작을수록 높은 순위이므로
# 그래프에서는 보기 좋게 음수로 바꿉니다.
rank_df["순위"] = (
    rank_df["순위"] * -1
)

st.line_chart(
    rank_df
)

st.markdown(
    f"""
    <div class="small-bubble">
        🕵️ <b>탐정:</b>
        {rank_story(history)}
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 🎞️ 스크린수
# ============================================================

st.markdown(
    '<div class="section-title">'
    '🎞️ 스크린수 추적'
    '</div>',
    unsafe_allow_html=True,
)

screen_df = pd.DataFrame(
    {
        "스크린수": [
            item["스크린수"]
            for item in history
        ]
    },
    index=[
        item["날짜"].strftime("%m/%d")
        for item in history
    ],
)

st.line_chart(
    screen_df
)

st.markdown(
    f"""
    <div class="small-bubble">
        🕵️ <b>탐정:</b>
        {screen_story(history)}
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 📽️ 상영횟수
# ============================================================

st.markdown(
    '<div class="section-title">'
    '📽️ 상영횟수 추적'
    '</div>',
    unsafe_allow_html=True,
)

show_df = pd.DataFrame(
    {
        "상영횟수": [
            item["상영횟수"]
            for item in history
        ]
    },
    index=[
        item["날짜"].strftime("%m/%d")
        for item in history
    ],
)

st.bar_chart(
    show_df
)

st.markdown(
    f"""
    <div class="small-bubble">
        🕵️ <b>탐정:</b>
        {show_story(history)}
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 📈 누적 관객
# ============================================================

st.markdown(
    '<div class="section-title">'
    '📈 누적 관객 추적'
    '</div>',
    unsafe_allow_html=True,
)

acc_df = pd.DataFrame(
    {
        "누적 관객수": [
            item["누적관객"]
            for item in history
        ]
    },
    index=[
        item["날짜"].strftime("%m/%d")
        for item in history
    ],
)

st.line_chart(
    acc_df
)

first_acc = history[0]["누적관객"]
last_acc = history[-1]["누적관객"]

st.markdown(
    f"""
    <div class="small-bubble">
        🕵️ <b>탐정:</b>
        최근 기록에서 누적 관객은
        <b>{comma(last_acc - first_acc)}명</b>
        증가했습니다.
        누적 관객은 시간이 지나면서 쌓이는 지표이므로
        증가 폭도 함께 살펴보는 게 좋습니다.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 📋 원본 데이터
# ============================================================

st.divider()

st.markdown(
    '<div class="section-title">'
    '📋 사건 기록 원본'
    '</div>',
    unsafe_allow_html=True,
)

table = pd.DataFrame(
    history
)

table["날짜"] = table["날짜"].apply(
    lambda x: x.strftime(
        "%Y-%m-%d"
    )
)

table = table[
    [
        "날짜",
        "순위",
        "관객수",
        "누적관객",
        "스크린수",
        "상영횟수",
    ]
].copy()


for column in [
    "관객수",
    "누적관객",
    "스크린수",
    "상영횟수",
]:

    table[column] = table[column].apply(
        lambda x: f"{x:,}"
    )


st.dataframe(
    table,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# 🔎 마지막 탐정 보고서
# ============================================================

st.divider()

st.markdown(
    '<div class="section-title">'
    '🔎 사건 파일 최종 정리'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="detective-bubble">

        <div class="detective-label">
            🕵️ 탐정의 최종 보고
        </div>

        <div class="detective-text">
            {detective_summary(history)}
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# ⚠️ 데이터 안내
# ============================================================

if failed_dates:

    st.warning(
        f"최근 14일 중 {len(failed
