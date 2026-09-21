import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


# ============================================================
# 🎬 영화 흥행 탐정
# KOBIS API만 사용하는 Streamlit 앱
# ============================================================

st.set_page_config(
    page_title="영화 흥행 탐정",
    page_icon="🎬",
    layout="wide",
)


# ============================================================
# KOBIS API 주소
# ============================================================

KOBIS_URL = (
    "https://www.kobis.or.kr/"
    "kobisopenapi/webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)


# ============================================================
# 한국 시간 기준 날짜 계산
# ============================================================

def korea_today():
    """한국 시간 기준 오늘 날짜를 가져옵니다."""
    return datetime.now(
        ZoneInfo("Asia/Seoul")
    ).date()


def yesterday():
    """한국 시간 기준 어제 날짜를 가져옵니다."""
    return korea_today() - timedelta(days=1)


def kobis_date(date_value):
    """날짜를 KOBIS용 YYYYMMDD로 바꿉니다."""
    return date_value.strftime("%Y%m%d")


# ============================================================
# 숫자 변환
# ============================================================

def to_int(value):
    """KOBIS에서 문자열로 오는 숫자를 정수로 바꿉니다."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def number(value):
    """숫자에 쉼표를 넣습니다."""
    return f"{value:,}"


# ============================================================
# KOBIS 하루 박스오피스 조회
# ============================================================

@st.cache_data(ttl=1800)
def get_daily_boxoffice(target_date):
    """KOBIS에서 특정 날짜의 일일 박스오피스를 가져옵니다."""

    # Secrets에 저장한 API 키를 가져옵니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except (KeyError, FileNotFoundError):
        return None, "KOBIS_KEY를 찾을 수 없습니다."

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
        return None, "KOBIS API 요청 시간이 초과되었습니다."

    except requests.exceptions.RequestException as error:
        return None, f"KOBIS API 연결에 실패했습니다.\n{error}"

    except json.JSONDecodeError:
        return None, "KOBIS에서 올바른 JSON 데이터를 받지 못했습니다."

    # 중요:
    # KOBIS는 인증키가 잘못되어도 HTTP 200을 줄 수 있습니다.
    # 따라서 faultInfo가 있는지 반드시 확인합니다.
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
            f"KOBIS API 오류입니다.\n"
            f"오류 코드: {code}\n"
            f"오류 내용: {message}"
        )

    result = data.get("boxOfficeResult")

    if not result:
        return None, "KOBIS 응답에 boxOfficeResult가 없습니다."

    movies = result.get(
        "dailyBoxOfficeList",
        [],
    )

    if not movies:
        return None, "해당 날짜의 영화 목록이 비어 있습니다."

    return movies, None


# ============================================================
# 특정 영화의 최근 데이터 가져오기
# ============================================================

@st.cache_data(ttl=1800)
def get_movie_history(
    movie_name,
    end_date,
    days=14,
):
    """
    선택한 영화의 최근 데이터를 가져옵니다.
    기본적으로 최근 14일을 확인합니다.
    """

    records = []
    failed_count = 0

    for i in range(days):

        target_day = (
            end_date - timedelta(days=i)
        )

        movies, error = get_daily_boxoffice(
            kobis_date(target_day)
        )

        # 해당 날짜의 API 요청에 문제가 있으면
        # 다음 날짜로 넘어갑니다.
        if error:
            failed_count += 1
            continue

        found = None

        for movie in movies:

            if movie.get("movieNm") == movie_name:
                found = movie
                break

        # 그날 박스오피스에 없었다면 넘어갑니다.
        if found is None:
            continue

        records.append(
            {
                "날짜": target_day,
                "순위": to_int(found.get("rank")),
                "영화명": found.get("movieNm", ""),
                "개봉일": found.get("openDt", ""),
                "관객수": to_int(found.get("audiCnt")),
                "누적관객": to_int(found.get("audiAcc")),
                "스크린수": to_int(found.get("scrnCnt")),
                "상영횟수": to_int(found.get("showCnt")),
            }
        )

    # 오래된 날짜부터 나오도록 정렬합니다.
    records.sort(
        key=lambda item: item["날짜"]
    )

    return records, failed_count


# ============================================================
# 변화율 계산
# ============================================================

def percentage_change(old, new):
    """두 숫자의 변화율을 계산합니다."""

    if old == 0:
        return None

    return ((new - old) / old) * 100


# ============================================================
# 재미있는 해설 만들기
# ============================================================

def audience_comment(history):

    if len(history) < 2:
        return "👥 아직 비교할 데이터가 충분하지 않아요."

    old = history[0]["관객수"]
    new = history[-1]["관객수"]

    rate = percentage_change(old, new)

    if rate is None:
        return "👥 관객수 변화를 계산하기 어렵습니다."

    if rate >= 30:
        return (
            f"🔥 관객수가 약 {rate:.1f}% 늘었습니다! "
            "최근 기록에서 관객 유입이 눈에 띄게 증가했습니다."
        )

    if rate >= 5:
        return (
            f"📈 관객수가 약 {rate:.1f}% 증가했습니다. "
            "조금씩 관객이 늘어나는 흐름입니다."
        )

    if rate > -5:
        return (
            "😐 관객수가 크게 움직이지 않았습니다. "
            "최근에는 비교적 안정적인 흐름입니다."
        )

    if rate > -30:
        return (
            f"📉 관객수가 약 {abs(rate):.1f}% 감소했습니다. "
            "최근 관객 유입이 조금 줄어든 모습입니다."
        )

    return (
        f"🍂 관객수가 약 {abs(rate):.1f}% 감소했습니다. "
        "처음 기록과 비교하면 관객 흐름이 꽤 줄어든 모습입니다."
    )


def rank_comment(history):

    if len(history) < 2:
        return "🏆 아직 순위 변화를 비교할 데이터가 부족합니다."

    old = history[0]["순위"]
    new = history[-1]["순위"]

    change = old - new

    if change >= 5:
        return (
            f"🚀 순위가 {change}계단 올라왔습니다! "
            "박스오피스에서 순위 변화가 크게 나타났습니다."
        )

    if change > 0:
        return (
            f"📈 순위가 {change}계단 상승했습니다."
        )

    if change <= -5:
        return (
            f"📉 순위가 {abs(change)}계단 내려갔습니다."
        )

    if change < 0:
        return (
            f"📉 순위가 {abs(change)}계단 하락했습니다."
        )

    return (
        "🧘 비교 기간 동안 순위가 그대로였습니다."
    )


def screen_comment(history):

    if len(history) < 2:
        return "🎞️ 스크린수 변화를 비교할 데이터가 부족합니다."

    old = history[0]["스크린수"]
    new = history[-1]["스크린수"]

    change = new - old

    if change >= 100:
        return (
            f"🎞️ 스크린이 {change:,}개 늘었습니다! "
            "극장 편성이 크게 확대된 모습입니다."
        )

    if change > 0:
        return (
            f"🎞️ 스크린이 {change:,}개 늘었습니다."
        )

    if change <= -100:
        return (
            f"🎞️ 스크린이 {abs(change):,}개 줄었습니다. "
            "극장 편성이 꽤 축소된 모습입니다."
        )

    if change < 0:
        return (
            f"🎞️ 스크린이 {abs(change):,}개 줄었습니다."
        )

    return (
        "🎞️ 스크린수에는 큰 변화가 없습니다."
    )


def final_comment(history):

    if len(history) < 2:
        return (
            "🕵️ 아직 사건 파일이 얇습니다. "
            "조금 더 데이터가 쌓이면 흐름이 잘 보일 거예요."
        )

    first = history[0]
    last = history[-1]

    audience_rate = percentage_change(
        first["관객수"],
        last["관객수"],
    )

    screen_change = (
        last["스크린수"]
        - first["스크린수"]
    )

    rank_change = (
        first["순위"]
        - last["순위"]
    )

    if (
        audience_rate is not None
        and audience_rate > 10
        and screen_change > 0
    ):
        return (
            "🕵️ **탐정의 한마디:** "
            "관객수와 스크린수가 함께 증가했습니다. "
            "최근 기록에서는 두 지표가 같은 방향으로 움직였습니다."
        )

    if (
        audience_rate is not None
        and audience_rate > 10
        and screen_change < 0
    ):
        return (
            "🕵️ **탐정의 한마디:** "
            "스크린수는 줄었지만 관객수는 증가했습니다. "
            "두 지표의 움직임이 서로 달랐습니다."
        )

    if (
        audience_rate is not None
        and audience_rate < -10
        and screen_change > 0
    ):
        return (
            "🕵️ **탐정의 한마디:** "
            "스크린수는 늘었지만 관객수는 감소했습니다. "
            "상영관 편성과 관객 흐름이 서로 다른 방향으로 움직였습니다."
        )

    if rank_change >= 3:
        return (
            f"🕵️ **탐정의 한마디:** "
            f"순위가 {rank_change}계단 상승했습니다. "
            "최근 순위 변화가 눈에 띄는 영화입니다."
        )

    if rank_change <= -3:
        return (
            f"🕵️ **탐정의 한마디:** "
            f"순위가 {abs(rank_change)}계단 하락했습니다. "
            "최근 순위 변화가 눈에 띕니다."
        )

    return (
        "🕵️ **탐정의 한마디:** "
        "관객수·순위·스크린수를 함께 살펴보면 "
        "최근 영화의 흐름을 더 잘 파악할 수 있습니다."
    )


# ============================================================
# 🎬 화면 시작
# ============================================================

st.title("🕵️ 영화 흥행 탐정")

st.write(
    "KOBIS 데이터를 이용해서 "
    "어제 상영된 영화들의 흥행 흐름을 살펴봅니다."
)

st.caption(
    "※ 한국 시간 기준으로 '어제'를 자동 계산합니다."
)


# ============================================================
# 어제 날짜 계산
# ============================================================

target_day = yesterday()

st.info(
    f"📅 분석 날짜: **{target_day.strftime('%Y년 %m월 %d일')}**"
)


# ============================================================
# 어제 박스오피스 가져오기
# ============================================================

with st.spinner(
    "🎬 어제의 영화 데이터를 가져오는 중..."
):

    movies, error = get_daily_boxoffice(
        kobis_date(target_day)
    )


# ============================================================
# API 오류 처리
# ============================================================

if error:

    st.error(
        "🚨 영화 데이터를 가져오지 못했습니다."
    )

    st.warning(error)

    st.markdown(
        """
### 🔧 다음 항목을 확인해 주세요

1. Streamlit Cloud의 **Settings → Secrets**를 열어주세요.
2. `KOBIS_KEY`가 정확하게 등록되어 있는지 확인해주세요.
3. KOBIS 인증키에 오타가 없는지 확인해주세요.
4. KOBIS Open API가 일시적으로 장애가 있는지 확인해주세요.
5. 잠시 후 앱을 새로고침해주세요.
        """
    )

    st.stop()


# ============================================================
# 영화 목록 확인
# ============================================================

movie_names = []

for movie in movies:

    name = movie.get("movieNm")

    if name:
        movie_names.append(name)


if not movie_names:

    st.warning(
        "🎬 현재 불러온 영화 목록이 비어 있습니다."
    )

    st.info(
        """
### 확인해 볼 것

- 한국 시간 기준 어제 날짜가 맞는지
- KOBIS에서 해당 날짜의 일일 박스오피스가 제공되는지
- KOBIS API 응답에 `dailyBoxOfficeList`가 있는지
        """
    )

    st.stop()


# ============================================================
# 영화 선택
# ============================================================

st.subheader("🎥 어떤 영화를 조사할까요?")

selected_movie = st.selectbox(
    "영화 선택",
    movie_names,
)


# ============================================================
# 선택한 영화 찾기
# ============================================================

selected_data = None

for movie in movies:

    if movie.get("movieNm") == selected_movie:
        selected_data = movie
        break


if selected_data is None:

    st.warning(
        "선택한 영화의 데이터를 찾을 수 없습니다."
    )

    st.stop()


# ============================================================
# 현재 데이터
# ============================================================

rank = to_int(
    selected_data.get("rank")
)

audience = to_int(
    selected_data.get("audiCnt")
)

audience_acc = to_int(
    selected_data.get("audiAcc")
)

screens = to_int(
    selected_data.get("scrnCnt")
)

shows = to_int(
    selected_data.get("showCnt")
)

open_date = selected_data.get(
    "openDt",
    "",
)


# ============================================================
# 영화 정보
# ============================================================

st.divider()

st.header(
    f"🎬 {selected_movie}"
)

if open_date:
    st.caption(
        f"개봉일: {open_date}"
    )


# ============================================================
# 핵심 지표 카드
# ============================================================

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "🏆 어제 순위",
        f"{rank}위",
    )

with col2:
    st.metric(
        "👥 어제 관객수",
        f"{number(audience)}명",
    )

with col3:
    st.metric(
        "🎟️ 누적 관객",
        f"{number(audience_acc)}명",
    )


col4, col5 = st.columns(2)

with col4:
    st.metric(
        "🎞️ 스크린수",
        f"{number(screens)}개",
    )

with col5:
    st.metric(
        "📽️ 상영횟수",
        f"{number(shows)}회",
    )


# ============================================================
# 최근 14일 기록
# ============================================================

st.divider()

st.subheader(
    "🕵️ 최근 14일 사건 기록"
)

with st.spinner(
    "과거 데이터를 조사하는 중..."
):

    history, failed_count = get_movie_history(
        selected_movie,
        target_day,
        14,
    )


if not history:

    st.warning(
        "최근 14일간 이 영화의 기록을 찾지 못했습니다."
    )

    st.info(
        """
다음 내용을 확인해주세요.

- 영화가 최근에 개봉했는지
- 최근 박스오피스에 계속 포함되어 있었는지
- KOBIS에서 해당 날짜의 데이터가 제공되는지
        """
    )

    st.stop()


if failed_count > 0:

    st.warning(
        f"최근 14일 중 {failed_count}일은 "
        "KOBIS 데이터를 가져오지 못했습니다."
    )


# ============================================================
# 탐정 브리핑
# ============================================================

st.subheader(
    "🕵️ 탐정의 현장 브리핑"
)

st.success(
    final_comment(history)
)


# ============================================================
# 관객수 그래프
# ============================================================

st.divider()

st.subheader(
    "👥 관객들은 어떻게 움직였을까?"
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

st.info(
    audience_comment(history)
)


# ============================================================
# 순위 그래프
# ============================================================

st.subheader(
    "🏆 순위는 어떻게 움직였을까?"
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

# 순위는 숫자가 작을수록 좋기 때문에
# 그래프에서는 -1위, -2위처럼 뒤집어서 표시합니다.
rank_df["순위"] = rank_df["순위"] * -1

st.line_chart(
    rank_df
)

st.info(
    rank_comment(history)
)


# ============================================================
# 스크린수 그래프
# ============================================================

st.subheader(
    "🎞️ 극장에서는 얼마나 상영했을까?"
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

st.info(
    screen_comment(history)
)


# ============================================================
# 상영횟수 그래프
# ============================================================

st.subheader(
    "📽️ 하루에 몇 번이나 상영됐을까?"
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

if len(history) >= 2:

    old_shows = history[0]["상영횟수"]
    new_shows = history[-1]["상영횟수"]

    show_change = new_shows - old_shows

    if show_change > 0:

        st.info(
            f"📽️ 비교 기간 동안 하루 상영횟수가 "
            f"{show_change:,}회 증가했습니다."
        )

    elif show_change < 0:

        st.info(
            f"📽️ 비교 기간 동안 하루 상영횟수가 "
            f"{abs(show_change):,}회 감소했습니다."
        )

    else:

        st.info(
            "📽️ 비교 기간 동안 상영횟수에 큰 변화가 없습니다."
        )


# ============================================================
# 누적 관객 그래프
# ============================================================

st.subheader(
    "🎟️ 누적 관객은 얼마나 쌓였을까?"
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

if len(history) >= 2:

    old_acc = history[0]["누적관객"]
    new_acc = history[-1]["누적관객"]

    acc_change = new_acc - old_acc

    st.info(
        f"🎟️ 최근 기록 기간 동안 누적 관객은 "
        f"{acc_change:,}명 증가했습니다."
    )


# ============================================================
# 상세 데이터 표
# ============================================================

st.divider()

st.subheader(
    "📋 데이터 원본"
)

table = pd.DataFrame(history)

table["날짜"] = table["날짜"].apply(
    lambda x: x.strftime("%Y-%m-%d")
)

table = table[
    [
        "날짜",
        "순위",
        "영화명",
        "개봉일",
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
# 마지막 한마디
# ============================================================

st.divider()

st.subheader(
    "🔎 오늘의 탐정 보고서"
)

st.success(
    final_comment(history)
)

st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS)"
)
