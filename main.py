import jsonimport json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


# =========================================================
# 1. Streamlit 기본 설정
# =========================================================

st.set_page_config(
    page_title="영화 흥행 탐정",
    page_icon="🕵️",
    layout="wide",
)


# =========================================================
# 2. KOBIS API 주소
# =========================================================

KOBIS_API_URL = (
    "https://www.kobis.or.kr/"
    "kobisopenapi/webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)


# =========================================================
# 3. 한국 시간 기준 날짜 함수
# =========================================================

def get_kst_today():
    """한국 시간 기준 오늘 날짜를 반환합니다."""

    now = datetime.now(
        ZoneInfo("Asia/Seoul")
    )

    return now.date()


def get_yesterday():
    """한국 시간 기준 어제 날짜를 반환합니다."""

    return get_kst_today() - timedelta(days=1)


def date_to_api_format(date_value):
    """
    날짜 객체를 KOBIS API가 사용하는
    YYYYMMDD 문자열로 바꿉니다.
    """

    return date_value.strftime("%Y%m%d")


def format_date_korean(date_value):
    """날짜를 화면에 보기 좋은 형태로 표시합니다."""

    return date_value.strftime(
        "%Y년 %m월 %d일"
    )


# =========================================================
# 4. KOBIS API에서 하루 데이터 가져오기
# =========================================================

@st.cache_data(ttl=60 * 30)
def get_daily_boxoffice(target_date):
    """
    특정 날짜의 KOBIS 일일 박스오피스를 가져옵니다.

    target_date:
        YYYYMMDD 형식 문자열

    반환:
        영화 목록, 오류 메시지
    """

    # -----------------------------------------------------
    # Secrets에서 KOBIS API 키 가져오기
    # -----------------------------------------------------

    try:

        api_key = st.secrets["KOBIS_KEY"]

    except (KeyError, FileNotFoundError):

        return None, (
            "KOBIS_KEY를 찾을 수 없습니다.\n\n"
            "Streamlit Cloud의 "
            "Settings → Secrets에 "
            "KOBIS_KEY가 등록되어 있는지 확인해 주세요."
        )

    # -----------------------------------------------------
    # API 요청
    # -----------------------------------------------------

    params = {
        "key": api_key,
        "targetDt": target_date,
    }

    try:

        response = requests.get(
            KOBIS_API_URL,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

    except requests.exceptions.Timeout:

        return None, (
            "KOBIS API 요청 시간이 초과되었습니다.\n\n"
            "잠시 후 다시 시도해 주세요."
        )

    except requests.exceptions.RequestException as error:

        return None, (
            "KOBIS API에 연결하지 못했습니다.\n\n"
            f"상세 오류: {error}\n\n"
            "인터넷 연결이나 KOBIS API 상태를 확인해 주세요."
        )

    except json.JSONDecodeError:

        return None, (
            "KOBIS API가 올바른 JSON 응답을 보내지 않았습니다.\n\n"
            "KOBIS API 상태를 확인해 주세요."
        )

    # -----------------------------------------------------
    # KOBIS는 인증키가 잘못되어도 HTTP 200을 반환할 수 있습니다.
    #
    # 따라서 HTTP 상태 코드만 확인하면 안 되고
    # faultInfo가 있는지도 확인해야 합니다.
    # -----------------------------------------------------

    if "faultInfo" in data:

        fault_info = data.get(
            "faultInfo",
            {},
        )

        error_code = (
            fault_info.get("resultCode")
            or fault_info.get("faultCode")
            or "알 수 없음"
        )

        error_message = (
            fault_info.get("resultMsg")
            or fault_info.get("faultString")
            or "KOBIS API 오류"
        )

        return None, (
            "KOBIS API에서 오류를 반환했습니다.\n\n"
            f"오류 코드: {error_code}\n"
            f"오류 내용: {error_message}\n\n"
            "KOBIS_KEY가 정확한지 확인해 주세요."
        )

    # -----------------------------------------------------
    # 정상 응답 처리
    # -----------------------------------------------------

    result = data.get(
        "boxOfficeResult"
    )

    if not result:

        return None, (
            "KOBIS 응답에 boxOfficeResult가 없습니다.\n\n"
            "KOBIS API의 응답 형식 또는 "
            "서비스 상태를 확인해 주세요."
        )

    movies = result.get(
        "dailyBoxOfficeList",
        [],
    )

    if not movies:

        return None, (
            "해당 날짜의 박스오피스 영화 목록이 없습니다.\n\n"
            "KOBIS 데이터가 정상적으로 집계되었는지 "
            "확인해 주세요."
        )

    return movies, None


# =========================================================
# 5. 최근 여러 날짜의 데이터 가져오기
# =========================================================

@st.cache_data(ttl=60 * 30)
def get_movie_history(
    movie_name,
    end_date,
    days=14,
):
    """
    선택한 영화의 최근 N일간 KOBIS 데이터를 수집합니다.

    KOBIS 일일 박스오피스 API를 날짜별로 조회합니다.
    """

    history = []
    errors = []

    # 오늘이 아니라 'end_date'부터 과거로 이동합니다.
    for offset in range(days):

        target_date = (
            end_date
            - timedelta(days=offset)
        )

        target_date_string = (
            date_to_api_format(
                target_date
            )
        )

        movies, error = get_daily_boxoffice(
            target_date_string
        )

        # 해당 날짜 API 오류
        if error:

            errors.append(
                {
                    "date": target_date,
                    "error": error,
                }
            )

            continue

        # 해당 날짜에서 선택한 영화를 찾습니다.
        found_movie = None

        for movie in movies:

            if movie.get("movieNm") == movie_name:

                found_movie = movie
                break

        # 영화가 해당 날짜 박스오피스에 없을 수 있습니다.
        if found_movie is None:

            continue

        # KOBIS에서 받은 데이터를 저장합니다.
        history.append(
            {
                "date": target_date,
                "rank": int(
                    found_movie.get(
                        "rank",
                        0,
                    )
                    or 0
                ),
                "movieNm": found_movie.get(
                    "movieNm",
                    movie_name,
                ),
                "openDt": found_movie.get(
                    "openDt",
                    "",
                ),
                "audiCnt": int(
                    found_movie.get(
                        "audiCnt",
                        0,
                    )
                    or 0
                ),
                "audiAcc": int(
                    found_movie.get(
                        "audiAcc",
                        0,
                    )
                    or 0
                ),
                "scrnCnt": int(
                    found_movie.get(
                        "scrnCnt",
                        0,
                    )
                    or 0
                ),
                "showCnt": int(
                    found_movie.get(
                        "showCnt",
                        0,
                    )
                    or 0
                ),
            }
        )

    # 날짜순으로 정렬합니다.
    history.sort(
        key=lambda item: item["date"]
    )

    return history, errors


# =========================================================
# 6. 숫자 포맷 함수
# =========================================================

def format_number(value):
    """숫자를 천 단위 쉼표로 표시합니다."""

    return f"{int(value):,}"


# =========================================================
# 7. 변화량 계산
# =========================================================

def calculate_change(history, column):
    """
    첫 번째 데이터와 마지막 데이터를 비교합니다.

    반환:
        처음 값
        마지막 값
        변화량
        변화율
    """

    if len(history) < 2:

        return None

    first_value = history[0][column]
    last_value = history[-1][column]

    change = (
        last_value - first_value
    )

    if first_value != 0:

        change_rate = (
            change
            / first_value
            * 100
        )

    else:

        change_rate = None

    return (
        first_value,
        last_value,
        change,
        change_rate,
    )


# =========================================================
# 8. 순위 변화 계산
# =========================================================

def calculate_rank_change(history):
    """
    순위는 숫자가 작을수록 좋습니다.

    예:
        10위 → 3위
        실제로는 7계단 상승
    """

    if len(history) < 2:

        return None

    first_rank = history[0]["rank"]
    last_rank = history[-1]["rank"]

    # 숫자가 감소하면 순위가 상승한 것입니다.
    improvement = (
        first_rank - last_rank
    )

    return (
        first_rank,
        last_rank,
        improvement,
    )


# =========================================================
# 9. 흥행 탐정 리포트 생성
# =========================================================

def make_detective_report(history):
    """
    실제 KOBIS 데이터의 변화만 가지고
    간단한 흥행 흐름 설명을 만듭니다.

    미래 흥행을 예측하지 않습니다.
    """

    if len(history) < 2:

        return (
            "아직 비교할 수 있는 날짜가 충분하지 않습니다. "
            "KOBIS에서 이 영화의 데이터가 쌓인 뒤 "
            "다시 확인해 주세요."
        )

    reports = []

    # -----------------------------------------------------
    # 관객수 변화
    # -----------------------------------------------------

    audience = calculate_change(
        history,
        "audiCnt",
    )

    if audience:

        first_value = audience[0]
        last_value = audience[1]
        change_rate = audience[3]

        if change_rate is not None:

            if change_rate > 20:

                reports.append(
                    f"최근 비교 기간의 일일 관객수가 "
                    f"{change_rate:.1f}% 증가했습니다."
                )

            elif change_rate < -20:

                reports.append(
                    f"최근 비교 기간의 일일 관객수가 "
                    f"{abs(change_rate):.1f}% 감소했습니다."
                )

            else:

                reports.append(
                    "최근 비교 기간의 일일 관객수는 "
                    "큰 폭의 변화가 나타나지 않았습니다."
                )

    # -----------------------------------------------------
    # 스크린수 변화
    # -----------------------------------------------------

    screen = calculate_change(
        history,
        "scrnCnt",
    )

    if screen:

        screen_change = screen[2]

        if screen_change > 0:

            reports.append(
                f"스크린수는 "
                f"{format_number(screen_change)}개 증가했습니다."
            )

        elif screen_change < 0:

            reports.append(
                f"스크린수는 "
                f"{format_number(abs(screen_change))}개 감소했습니다."
            )

        else:

            reports.append(
                "스크린수에는 변화가 없었습니다."
            )

    # -----------------------------------------------------
    # 순위 변화
    # -----------------------------------------------------

    rank_change = calculate_rank_change(
        history
    )

    if rank_change:

        improvement = rank_change[2]

        if improvement > 0:

            reports.append(
                f"박스오피스 순위는 "
                f"{improvement}계단 상승했습니다."
            )

        elif improvement < 0:

            reports.append(
                f"박스오피스 순위는 "
                f"{abs(improvement)}계단 하락했습니다."
            )

        else:

            reports.append(
                "박스오피스 순위에는 변화가 없었습니다."
            )

    return " ".join(reports)


# =========================================================
# 10. 페이지 제목
# =========================================================

st.title("🕵️ 영화 흥행 탐정")

st.write(
    "KOBIS의 실제 박스오피스 데이터를 이용해 "
    "영화의 최근 흥행 흐름을 살펴봅니다."
)

st.caption(
    "※ 미래 흥행을 예측하지 않고 "
    "KOBIS에서 확인되는 실제 데이터의 변화만 분석합니다."
)


# =========================================================
# 11. 조회 기준 날짜
# =========================================================

yesterday = get_yesterday()

st.info(
    "현재는 한국 시간 기준 "
    f"{format_date_korean(yesterday)}의 "
    "박스오피스를 기본으로 조회합니다."
)


# =========================================================
# 12. 어제 박스오피스 가져오기
# =========================================================

with st.spinner(
    "KOBIS에서 박스오피스를 가져오는 중입니다..."
):

    yesterday_movies, error = (
        get_daily_boxoffice(
            date_to_api_format(
                yesterday
            )
        )
    )


if error:

    st.error(
        "KOBIS 데이터를 가져오지 못했습니다."
    )

    st.warning(error)

    st.info(
        "확인할 내용:\n\n"
        "1. Streamlit Cloud → Settings → Secrets에서 "
        "KOBIS_KEY가 등록되어 있는지 확인\n"
        "2. KOBIS 인증키가 정확한지 확인\n"
        "3. KOBIS Open API 상태 확인\n"
        "4. 잠시 후 새로고침"
    )

    st.stop()


# =========================================================
# 13. 영화 목록 만들기
# =========================================================

movie_names = [
    movie.get("movieNm")
    for movie in yesterday_movies
    if movie.get("movieNm")
]


if not movie_names:

    st.warning(
        "어제의 영화 목록이 비어 있습니다."
    )

    st.info(
        "KOBIS의 어제 박스오피스 데이터가 "
        "정상적으로 집계되었는지 확인해 주세요."
    )

    st.stop()


# =========================================================
# 14. 영화 선택
# =========================================================

st.subheader(
    "🔎 조사할 영화를 선택하세요."
)

selected_movie = st.selectbox(
    "영화",
    options=movie_names,
)


# =========================================================
# 15. 선택 영화의 최신 데이터 찾기
# =========================================================

selected_latest = None

for movie in yesterday_movies:

    if movie.get("movieNm") == selected_movie:

        selected_latest = movie
        break


if selected_latest is None:

    st.warning(
        "선택한 영화의 상세 데이터를 찾을 수 없습니다."
    )

    st.stop()


# 숫자 변환
latest_rank = int(
    selected_latest.get(
        "rank",
        0,
    )
    or 0
)

latest_audience = int(
    selected_latest.get(
        "audiCnt",
        0,
    )
    or 0
)

latest_acc = int(
    selected_latest.get(
        "audiAcc",
        0,
    )
    or 0
)

latest_screen = int(
    selected_latest.get(
        "scrnCnt",
        0,
    )
    or 0
)

latest_show = int(
    selected_latest.get(
        "showCnt",
        0,
    )
    or 0
)

latest_open_date = selected_latest.get(
    "openDt",
    "",
)


# =========================================================
# 16. 영화 기본 정보
# =========================================================

st.divider()

st.header(
    f"🎬 {selected_movie}"
)

if latest_open_date:

    st.caption(
        f"개봉일: {latest_open_date}"
    )


# =========================================================
# 17. 현재 주요 지표
# =========================================================

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "어제 박스오피스 순위",
        f"{latest_rank}위",
    )

with col2:

    st.metric(
        "어제 관객수",
        f"{format_number(latest_audience)}명",
    )

with col3:

    st.metric(
        "누적 관객수",
        f"{format_number(latest_acc)}명",
    )


col4, col5 = st.columns(2)

with col4:

    st.metric(
        "스크린수",
        f"{format_number(latest_screen)}개",
    )

with col5:

    st.metric(
        "상영횟수",
        f"{format_number(latest_show)}회",
    )


# =========================================================
# 18. 최근 데이터 가져오기
# =========================================================

st.divider()

st.subheader(
    "🔍 흥행 기록 조사 중..."
)

with st.spinner(
    "최근 14일의 KOBIS 데이터를 확인하고 있습니다..."
):

    history, history_errors = (
        get_movie_history(
            selected_movie,
            yesterday,
            days=14,
        )
    )


# 데이터가 아예 없는 경우
if not history:

    st.warning(
        "선택한 영화의 최근 기록을 찾지 못했습니다."
    )

    st.info(
        "다음 사항을 확인해 주세요.\n\n"
        "• 해당 영화가 최근 박스오피스 순위에 있었는지\n"
        "• 영화명이 KOBIS에서 정확하게 조회되는지\n"
        "• 최근 날짜의 KOBIS 데이터가 정상적으로 제공되는지"
    )

    st.stop()


# 일부 날짜에 오류가 있었으면 안내
if history_errors:

    st.warning(
        f"최근 조회 중 {len(history_errors)}개 날짜의 "
        "데이터를 가져오지 못했습니다."
    )

    st.caption(
        "데이터가 정상적으로 확인된 날짜만 "
        "그래프에 표시합니다."
    )


# =========================================================
# 19. History DataFrame
# =========================================================

history_df = pd.DataFrame(
    history
)

history_df = history_df.sort_values(
    "date"
).reset_index(drop=True)


# 날짜를 문자열로 변경
history_df["date_label"] = (
    history_df["date"]
    .apply(
        lambda value: value.strftime(
            "%m/%d"
        )
    )
)


# =========================================================
# 20. 탐정 리포트
# =========================================================

st.subheader(
    "🕵️ 흥행 탐정 리포트"
)

report = make_detective_report(
    history
)

st.info(report)


# =========================================================
# 21. 최근 기록 요약
# =========================================================

st.subheader(
    "📋 최근 기록"
)

first_record = history[0]
last_record = history[-1]

period_start = first_record["date"]
period_end = last_record["date"]

st.caption(
    f"{format_date_korean(period_start)} ~ "
    f"{format_date_korean(period_end)}"
)


# =========================================================
# 22. 최근 관객수 변화
# =========================================================

st.subheader(
    "👥 일일 관객수 추이"
)

audience_chart = history_df[
    [
        "date_label",
        "audiCnt",
    ]
].copy()

audience_chart = audience_chart.set_index(
    "date_label"
)

audience_chart.columns = [
    "일일 관객수"
]

st.line_chart(
    audience_chart,
    y="일일 관객수",
    y_label="관객수",
)


# =========================================================
# 23. 누적 관객수
# =========================================================

st.subheader(
    "📈 누적 관객수 추이"
)

acc_chart = history_df[
    [
        "date_label",
        "audiAcc",
    ]
].copy()

acc_chart = acc_chart.set_index(
    "date_label"
)

acc_chart.columns = [
    "누적 관객수"
]

st.line_chart(
    acc_chart,
    y="누적 관객수",
    y_label="누적 관객수",
)


# =========================================================
# 24. 순위 변화
# =========================================================

st.subheader(
    "🏆 박스오피스 순위 변화"
)

rank_chart = history_df[
    [
        "date_label",
        "rank",
    ]
].copy()

rank_chart = rank_chart.set_index(
    "date_label"
)

rank_chart.columns = [
    "순위"
]

# 순위는 숫자가 작을수록 높은 순위이므로
# 그래프에서 1위가 위쪽에 오도록 뒤집습니다.
rank_chart["순위 표시"] = (
    rank_chart["순위"] * -1
)

st.line_chart(
    rank_chart[
        ["순위 표시"]
    ],
    y="순위 표시",
    y_label="순위",
)


# =========================================================
# 25. 스크린수와 상영횟수
# =========================================================

col1, col2 = st.columns(2)


with col1:

    st.subheader(
        "🎞️ 스크린수 변화"
    )

    screen_chart = history_df[
        [
            "date_label",
            "scrnCnt",
        ]
    ].copy()

    screen_chart = screen_chart.set_index(
        "date_label"
    )

    screen_chart.columns = [
        "스크린수"
    ]

    st.line_chart(
        screen_chart,
        y="스크린수",
        y_label="스크린수",
    )


with col2:

    st.subheader(
        "📽️ 상영횟수 변화"
    )

    show_chart = history_df[
        [
            "date_label",
            "showCnt",
        ]
    ].copy()

    show_chart = show_chart.set_index(
        "date_label"
    )

    show_chart.columns = [
        "상영횟수"
    ]

    st.line_chart(
        show_chart,
        y="상영횟수",
        y_label="상영횟수",
    )


# =========================================================
# 26. 시작일과 마지막 날 비교
# =========================================================

st.divider()

st.subheader(
    "⚖️ 기간 시작과 현재 비교"
)


compare1, compare2, compare3 = st.columns(3)


# ---------------------------------------------------------
# 관객수 비교
# ---------------------------------------------------------

audience_change = calculate_change(
    history,
    "audiCnt",
)

with compare1:

    st.write(
        "**일일 관객수**"
    )

    if audience_change:

        first_value = audience_change[0]
        last_value = audience_change[1]

        st.metric(
            "현재",
            f"{format_number(last_value)}명",
            delta=f"{format_number(last_value - first_value)}명",
        )

    else:

        st.write(
            "비교 데이터 부족"
        )


# ---------------------------------------------------------
# 스크린수 비교
# ---------------------------------------------------------

screen_change = calculate_change(
    history,
    "scrnCnt",
)

with compare2:

    st.write(
        "**스크린수**"
    )

    if screen_change:

        first_value = screen_change[0]
        last_value = screen_change[1]

        st.metric(
            "현재",
            f"{format_number(last_value)}개",
            delta=f"{format_number(last_value - first_value)}개",
        )

    else:

        st.write(
            "비교 데이터 부족"
        )


# ---------------------------------------------------------
# 순위 비교
# ---------------------------------------------------------

rank_change = calculate_rank_change(
    history
)

with compare3:

    st.write(
        "**박스오피스 순위**"
    )

    if rank_change:

        first_rank = rank_change[0]
        last_rank = rank_change[1]

        improvement = rank_change[2]

        if improvement > 0:

            delta_text = (
                f"{improvement}계단 상승"
            )

        elif improvement < 0:

            delta_text = (
                f"{abs(improvement)}계단 하락"
            )

        else:

            delta_text = "변화 없음"

        st.metric(
            "현재",
            f"{last_rank}위",
            delta=delta_text,
        )

    else:

        st.write(
            "비교 데이터 부족"
        )


# =========================================================
# 27. 상세 데이터 표
# =========================================================

st.divider()

st.subheader(
    "📊 상세 흥행 기록"
)

display_df = history_df[
    [
        "date",
        "rank",
        "audiCnt",
        "audiAcc",
        "scrnCnt",
        "showCnt",
    ]
].copy()


display_df["date"] = (
    display_df["date"]
    .apply(
        lambda value: value.strftime(
            "%Y-%m-%d"
        )
    )
)


display_df.columns = [
    "날짜",
    "순위",
    "일일 관객수",
    "누적 관객수",
    "스크린수",
    "상영횟수",
]


# 숫자에 천 단위 쉼표를 적용합니다.
for column in [
    "일일 관객수",
    "누적 관객수",
    "스크린수",
    "상영횟수",
]:

    display_df[column] = (
        display_df[column]
        .apply(
            lambda value: f"{int(value):,}"
        )
    )


st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# 28. 데이터 출처
# =========================================================

st.divider()

st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS)"
)

st.caption(
    "※ 이 앱은 KOBIS에서 제공하는 실제 과거 데이터를 "
    "시각화하고 비교합니다."
)

st.caption(
    "※ 그래프와 리포트는 미래 흥행 결과를 예측하지 않습니다."
)
