import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


# ============================================================
# 🎬 영화 흥행 탐정
# KOBIS API 하나만 사용하는 Streamlit 앱
# ============================================================

st.set_page_config(
    page_title="영화 흥행 탐정",
    page_icon="🕵️",
    layout="wide",
)


# ============================================================
# 1. KOBIS API 주소
# ============================================================

KOBIS_URL = (
    "https://www.kobis.or.kr/"
    "kobisopenapi/webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)


# ============================================================
# 2. 한국 시간 기준 날짜
# ============================================================

def get_korea_today():
    """한국 시간 기준 오늘 날짜를 가져옵니다."""

    return datetime.now(
        ZoneInfo("Asia/Seoul")
    ).date()


def get_yesterday():
    """한국 시간 기준 어제 날짜를 가져옵니다."""

    return get_korea_today() - timedelta(days=1)


def to_kobis_date(date_value):
    """날짜를 KOBIS용 YYYYMMDD 형태로 변환합니다."""

    return date_value.strftime("%Y%m%d")


def pretty_date(date_value):
    """날짜를 보기 좋은 한국어 형태로 표시합니다."""

    return date_value.strftime(
        "%Y년 %m월 %d일"
    )


# ============================================================
# 3. 숫자 변환
# ============================================================

def safe_int(value):
    """KOBIS의 문자열 숫자를 정수로 변환합니다."""

    try:
        return int(value)

    except (ValueError, TypeError):
        return 0


def comma(value):
    """숫자에 천 단위 쉼표를 표시합니다."""

    return f"{int(value):,}"


# ============================================================
# 4. KOBIS에서 하루 박스오피스 가져오기
# ============================================================

@st.cache_data(ttl=1800)
def get_boxoffice(target_date):
    """
    KOBIS 일일 박스오피스 API를 호출합니다.

    target_date는 YYYYMMDD 형태입니다.
    """

    # --------------------------------------------------------
    # Streamlit Secrets에서 인증키를 가져옵니다.
    # 실제 키를 코드에 작성하지 않습니다.
    # --------------------------------------------------------

    try:
        api_key = st.secrets["KOBIS_KEY"]

    except (KeyError, FileNotFoundError):

        return None, (
            "KOBIS_KEY를 찾을 수 없습니다."
        )

    # API에 전달할 값입니다.
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
            f"상세 오류: {error}"
        )

    except json.JSONDecodeError:

        return None, (
            "KOBIS에서 올바른 JSON 데이터를 "
            "받지 못했습니다."
        )

    # --------------------------------------------------------
    # KOBIS는 인증키가 틀려도 HTTP 200을 반환할 수 있습니다.
    # 따라서 faultInfo를 반드시 확인합니다.
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
            f"KOBIS API 오류입니다.\n\n"
            f"오류 코드: {code}\n"
            f"오류 내용: {message}"
        )

    # 정상적인 박스오피스 결과를 가져옵니다.
    result = data.get("boxOfficeResult")

    if not result:

        return None, (
            "KOBIS 응답에 boxOfficeResult가 없습니다."
        )

    movies = result.get(
        "dailyBoxOfficeList",
        [],
    )

    if not movies:

        return None, (
            "해당 날짜의 영화 목록이 비어 있습니다."
        )

    return movies, None


# ============================================================
# 5. 특정 영화의 최근 기록 가져오기
# ============================================================

@st.cache_data(ttl=1800)
def get_movie_history(
    movie_name,
    end_date_string,
    days=14,
):
    """
    선택한 영화의 최근 데이터를 가져옵니다.

    KOBIS 일일 박스오피스를 날짜별로 조회합니다.
    """

    end_date = datetime.strptime(
        end_date_string,
        "%Y-%m-%d",
    ).date()

    records = []
    failed_dates = []

    # 최근 14일을 하나씩 확인합니다.
    for i in range(days):

        target_date = (
            end_date - timedelta(days=i)
        )

        target = to_kobis_date(
            target_date
        )

        movies, error = get_boxoffice(
            target
        )

        # API 요청 자체가 실패한 경우
        if error:

            failed_dates.append(
                target_date
            )

            continue

        found = None

        # 해당 날짜의 영화 목록에서
        # 사용자가 선택한 영화를 찾습니다.
        for movie in movies:

            if movie.get("movieNm") == movie_name:

                found = movie
                break

        # 그날 박스오피스에 없으면 건너뜁니다.
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

    # 날짜가 오래된 것부터 최신 순서가 되도록 정렬합니다.
    records.sort(
        key=lambda x: x["날짜"]
    )

    return records, failed_dates


# ============================================================
# 6. 변화율 계산
# ============================================================

def change_rate(first, last):
    """처음 값과 마지막 값의 변화율을 계산합니다."""

    if first == 0:
        return None

    return (
        (last - first)
        / first
        * 100
    )


# ============================================================
# 7. 관객수 해설
# ============================================================

def audience_story(history):

    if len(history) < 2:

        return (
            "👥 아직 비교할 날짜가 충분하지 않아요. "
            "조금 더 데이터가 쌓이면 관객 흐름을 볼 수 있습니다."
        )

    first = history[0]["관객수"]
    last = history[-1]["관객수"]

    rate = change_rate(
        first,
        last,
    )

    if rate is None:

        return (
            "👥 관객수 변화를 계산하기 어렵습니다."
        )

    if rate >= 50:

        return (
            f"🔥 관객수가 {rate:.1f}% 증가했어요! "
            "최근 비교 기간에 관객 유입이 크게 늘어난 모습입니다."
        )

    if rate >= 20:

        return (
            f"📈 관객수가 {rate:.1f}% 증가했어요. "
            "최근 관객 흐름이 꽤 활발해졌습니다."
        )

    if rate >= 5:

        return (
            f"🙂 관객수가 {rate:.1f}% 늘었어요. "
            "큰 폭은 아니지만 증가하는 흐름입니다."
        )

    if rate > -5:

        return (
            "😐 관객수가 큰 폭으로 움직이지 않았어요. "
            "최근 관객 흐름이 비교적 안정적입니다."
        )

    if rate > -20:

        return (
            f"📉 관객수가 {abs(rate):.1f}% 감소했어요. "
            "최근 관객 유입이 조금씩 줄어드는 모습입니다."
        )

    if rate > -50:

        return (
            f"🍂 관객수가 {abs(rate):.1f}% 감소했어요. "
            "초반에 비해 관객 흐름이 약해진 모습입니다."
        )

    return (
        f"🌙 관객수가 {abs(rate):.1f}% 감소했어요. "
        "최근 관객 유입이 크게 줄어든 상태입니다."
    )


# ============================================================
# 8. 순위 해설
# ============================================================

def rank_story(history):

    if len(history) < 2:

        return (
            "🏆 아직 비교할 순위 데이터가 충분하지 않습니다."
        )

    first = history[0]["순위"]
    last = history[-1]["순위"]

    # 숫자가 작아질수록 순위가 올라간 것입니다.
    difference = first - last

    if difference >= 5:

        return (
            f"🚀 순위가 {difference}계단 상승했어요! "
            "박스오피스에서 존재감이 커진 흐름입니다."
        )

    if difference > 0:

        return (
            f"📈 순위가 {difference}계단 상승했어요. "
            "조금씩 상위권으로 올라온 모습입니다."
        )

    if difference <= -5:

        return (
            f"📉 순위가 {abs(difference)}계단 하락했어요. "
            "최근 박스오피스 순위가 꽤 움직였습니다."
        )

    if difference < 0:

        return (
            f"📉 순위가 {abs(difference)}계단 하락했어요."
        )

    return (
        "🧘 순위가 그대로예요. "
        "최근 비교 기간 동안 큰 순위 변화가 없었습니다."
    )


# ============================================================
# 9. 스크린수 해설
# ============================================================

def screen_story(history):

    if len(history) < 2:

        return (
            "🎞️ 스크린수 변화를 비교할 데이터가 부족합니다."
        )

    first = history[0]["스크린수"]
    last = history[-1]["스크린수"]

    difference = last - first

    if difference >= 100:

        return (
            f"🎞️ 스크린이 {difference:,}개 늘었어요! "
            "극장 편성이 크게 확대된 구간입니다."
        )

    if difference > 0:

        return (
            f"🎞️ 스크린이 {difference:,}개 늘었어요. "
            "상영관 배정이 확대된 모습입니다."
        )

    if difference <= -100:

        return (
            f"🎞️ 스크린이 {abs(difference):,}개 줄었어요. "
            "극장 편성이 상당히 축소된 흐름입니다."
        )

    if difference < 0:

        return (
            f"🎞️ 스크린이 {abs(difference):,}개 줄었어요. "
            "상영관 배정이 조금 감소했습니다."
        )

    return (
        "🎞️ 스크린수가 거의 그대로예요. "
        "극장 편성이 비교적 안정적으로 유지되고 있습니다."
    )


# ============================================================
# 10. 상영횟수 해설
# ============================================================

def show_story(history):

    if len(history) < 2:

        return (
            "📽️ 상영횟수를 비교할 데이터가 부족합니다."
        )

    first = history[0]["상영횟수"]
    last = history[-1]["상영횟수"]

    difference = last - first

    if difference > 100:

        return (
            f"📽️ 하루 상영횟수가 {difference:,}회 늘었어요! "
            "극장에서 이 영화를 만날 수 있는 편성이 크게 늘었습니다."
        )

    if difference > 0:

        return (
            f"📽️ 상영횟수가 {difference:,}회 증가했어요. "
            "상영 편성이 조금 확대됐습니다."
        )

    if difference < -100:

        return (
            f"📽️ 상영횟수가 {abs(difference):,}회 줄었어요. "
            "상영 편성이 눈에 띄게 감소했습니다."
        )

    if difference < 0:

        return (
            f"📽️ 상영횟수가 {abs(difference):,}회 감소했어요."
        )

    return (
        "📽️ 상영횟수는 큰 변화가 없습니다."
    )


# ============================================================
# 11. 스크린당 관객수 해설
# ============================================================

def efficiency_story(history):

    if not history:
        return ""

    latest = history[-1]

    audience = latest["관객수"]
    screens = latest["스크린수"]

    if screens == 0:

        return (
            "🎯 스크린수가 0이라 스크린당 관객수를 "
            "계산할 수 없습니다."
        )

    per_screen = audience / screens

    return (
        f"🎯 어제 기준 스크린 1개당 약 "
        f"{per_screen:.0f}명의 관객이 집계됐어요. "
        "관객수와 스크린수를 함께 보면 "
        "영화의 현재 흐름을 조금 더 입체적으로 볼 수 있습니다."
    )


# ============================================================
# 12. 탐정의 종합 분석
# ============================================================

def detective_summary(history):

    if len(history) < 2:

        return (
            "🕵️ 아직 사건 파일이 얇습니다. "
            "조금 더 날짜가 쌓이면 변화가 더 잘 보일 거예요."
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
            "🕵️ **탐정의 한마디:** "
            "관객과 스크린이 함께 올라가는 흐름이 포착됐습니다. "
            "최근 비교 기간에는 극장 편성과 관객 흐름이 "
            "같은 방향으로 움직였습니다."
        )

    # 관객 증가 + 스크린 감소
    if (
        audience_rate is not None
        and audience_rate > 10
        and screen_difference < 0
    ):

        return (
            "🕵️ **탐정의 한마디:** "
            "스크린은 줄었는데 관객수는 늘었습니다. "
            "최근 데이터에서는 상영관 규모보다 "
            "관객수 변화가 더 눈에 띕니다."
        )

    # 관객 감소 + 스크린 증가
    if (
        audience_rate is not None
        and audience_rate < -10
        and screen_difference > 0
    ):

        return (
            "🕵️ **탐정의 한마디:** "
            "스크린은 늘었지만 관객수는 감소했습니다. "
            "상영관 확대와 관객 유입이 같은 방향으로 "
            "움직이지 않은 구간입니다."
        )

    # 순위 상승
    if rank_difference >= 3:

        return (
            "🕵️ **탐정의 한마디:** "
            f"박스오피스 순위가 {rank_difference}계단 올라왔습니다. "
            "최근 비교 기간의 순위 변화가 눈에 띕니다."
        )

    # 순위 하락
    if rank_difference <= -3:

        return (
            "🕵️ **탐정의 한마디:** "
            f"박스오피스 순위가 {abs(rank_difference)}계단 내려왔습니다. "
            "최근 순위 흐름에 변화가 나타났습니다."
        )

    return (
        "🕵️ **탐정의 한마디:** "
        "최근 데이터에서는 관객수·스크린수·순위를 "
        "함께 살펴보는 것이 좋겠습니다."
    )


# ============================================================
# 13. 앱 제목
# ============================================================

st.title("🕵️ 영화 흥행 탐정")

st.write(
    "영화 한 편을 선택하면 KOBIS 데이터를 추적해서 "
    "최근 흥행 흐름을 재미있게 분석해드립니다."
)

st.caption(
    "KOBIS 일일 박스오피스 데이터를 기반으로 합니다. "
    "미래 흥행을 예측하지 않고 실제 관측 데이터를 설명합니다."
)


# ============================================================
# 14. 한국 시간 기준 어제
# ============================================================

yesterday = get_yesterday()

st.info(
    f"📅 조사 기준일: **{pretty_date(yesterday)}** "
    "(한국 시간 기준)"
)


# ============================================================
# 15. 어제 박스오피스 조회
# ============================================================

with st.spinner(
    "🕵️ 어제의 박스오피스 사건 파일을 여는 중..."
):

    movies, error = get_boxoffice(
        to_kobis_date(yesterday)
    )


# API 오류
if error:

    st.error(
        "🚨 KOBIS 데이터를 가져오지 못했습니다."
    )

    st.warning(error)

    st.info(
        """
### 🔧 먼저 확인해 주세요

- Streamlit Cloud → **Settings → Secrets**에 `KOBIS_KEY`가 있는지 확인
- KOBIS 인증키에 오타가 없는지 확인
- KOBIS Open API가 정상적으로 작동하는지 확인
- 잠시 후 페이지를 새로고침
        """
    )

    st.stop()


# ============================================================
# 16. 영화 목록 만들기
# ============================================================

movie_names = [
    movie.get("movieNm")
    for movie in movies
    if movie.get("movieNm")
]


if not movie_names:

    st.warning(
        "🎬 조사할 영화 목록이 없습니다."
    )

    st.info(
        "한국 시간 기준 어제의 KOBIS 박스오피스 "
        "데이터가 정상적으로 집계되었는지 확인해 주세요."
    )

    st.stop()


# ============================================================
# 17. 영화 선택
# ============================================================

st.subheader(
    "🔎 사건 파일을 선택하세요"
)

selected_movie = st.selectbox(
    "분석할 영화",
    movie_names,
)


# ============================================================
# 18. 선택한 영화의 최신 데이터 찾기
# ============================================================

latest = None

for movie in movies:

    if movie.get("movieNm") == selected_movie:

        latest = movie
        break


if latest is None:

    st.warning(
        "선택한 영화의 데이터를 찾을 수 없습니다."
    )

    st.stop()


# ============================================================
# 19. 최신 데이터 숫자로 변환
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
# 20. 영화 정보
# ============================================================

st.divider()

st.header(
    f"🎬 {selected_movie}"
)

if release_date:

    st.caption(
        f"개봉일: {release_date}"
    )


# ============================================================
# 21. 현재 지표
# ============================================================

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "🏆 어제 순위",
        f"{current_rank}위",
    )

with col2:

    st.metric(
        "👥 어제 관객수",
        f"{comma(current_audience)}명",
    )

with col3:

    st.metric(
        "🎟️ 누적 관객",
        f"{comma(current_acc)}명",
    )


col4, col5 = st.columns(2)

with col4:

    st.metric(
        "🎞️ 스크린수",
        f"{comma(current_screens)}개",
    )

with col5:

    st.metric(
        "📽️ 상영횟수",
        f"{comma(current_shows)}회",
    )


# ============================================================
# 22. 최근 14일 데이터 조회
# ============================================================

st.divider()

st.subheader(
    "🗂️ 최근 14일 사건 기록"
)

with st.spinner(
    "과거 기록을 뒤지는 중..."
):

    history, failed_dates = get_movie_history(
        selected_movie,
        yesterday.isoformat(),
        days=14,
    )


if not history:

    st.warning(
        "최근 기록을 찾지 못했습니다."
    )

    st.info(
        """
다음 사항을 확인해 주세요.

- 이 영화가 최근 박스오피스에 포함되어 있었는지
- 영화가 개봉한 지 얼마 되지 않았는지
- KOBIS에서 해당 날짜의 데이터가 제공되는지
        """
    )

    st.stop()


if failed_dates:

    st.warning(
        f"최근 14일 중 {len(failed_dates)}일의 "
        "데이터 요청에 문제가 있었습니다."
    )

    st.caption(
        "정상적으로 받아온 데이터만 분석합니다."
    )


# ============================================================
# 23. 탐정의 현장 브리핑
# ============================================================

st.subheader(
    "🕵️ 탐정의 현장 브리핑"
)

st.success(
    detective_summary(history)
)


# ============================================================
# 24. 관객수 그래프
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
    audience_story(history)
)


# ============================================================
# 25. 순위 그래프
# ============================================================

st.subheader(
    "🏆 박스오피스에서 올라갔을까, 내려갔을까?"
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

# 1위가 그래프에서 위쪽에 오도록 음수로 표시합니다.
rank_df["순위"] = (
    rank_df["순위"] * -1
)

st.line_chart(
    rank_df
)

st.info(
    rank_story(history)
)


# ============================================================
# 26. 스크린수 그래프
# ============================================================

st.subheader(
    "🎞️ 극장에서는 이 영화를 얼마나 배정했을까?"
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
    screen_story(history)
)


# ============================================================
# 27. 상영횟수 그래프
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

st.info(
    show_story(history)
)


# ============================================================
# 28. 누적 관객 그래프
# ============================================================

st.subheader(
    "📈 관객은 얼마나 쌓였을까?"
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

st.info(
    f"🎟️ 최근 기록에서 누적 관객은 "
    f"**{comma(last_acc - first_acc)}명** 증가했습니다."
)


# ============================================================
# 29. 스크린당 관객 그래프
# ============================================================

st.subheader(
    "🎯 스크린 하나당 관객은 얼마나 모였을까?"
)

efficiency_values = []

for item in history:

    screens = item["스크린수"]

    if screens > 0:

        value = (
            item["관객수"]
            / screens
        )

    else:

        value = 0

    efficiency_values.append(
        value
    )


efficiency_df = pd.DataFrame(
    {
        "스크린당 관객수": efficiency_values
    },
    index=[
        item["날짜"].strftime("%m/%d")
        for item in history
    ],
)

st.line_chart(
    efficiency_df
)

st.info(
    efficiency_story(history)
)


# ============================================================
# 30. 상세 데이터
# ============================================================

st.divider()

st.subheader(
    "📋 사건 기록 원본"
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
# 31. 최종 탐정 보고서
# ============================================================

st.divider()

st.subheader(
    "🔎 탐정의 최종 보고서"
)

st.success(
    detective_summary(history)
)

st.caption(
    "※ 위 내용은 KOBIS에서 확인된 실제 과거 데이터를 "
    "요약한 것입니다. 미래 흥행 결과를 예측하지 않습니다."
)


# ============================================================
# 32. 데이터 출처
# ============================================================

st.divider()

st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS)"
)

st.caption(
    f"데이터 기준일: {pretty_date(yesterday)}"
)
