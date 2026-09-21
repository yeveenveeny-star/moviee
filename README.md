import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------

# 브라우저 탭 제목과 아이콘을 설정합니다.
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)


# KOBIS 일일 박스오피스 API 주소입니다.
API_URL = (
    "https://www.kobis.or.kr/"
    "kobisopenapi/webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)


# ---------------------------------------------------------
# 날짜 계산
# ---------------------------------------------------------

def get_yesterday_kst():
    """한국 시간 기준으로 '어제'의 날짜를 YYYYMMDD 문자열로 반환합니다."""

    # 배포 서버가 어느 나라 시간으로 설정되어 있든 상관없이
    # 한국 표준시(Asia/Seoul)를 기준으로 현재 시간을 가져옵니다.
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))

    # 한국 시간 기준으로 하루를 빼서 어제 날짜를 구합니다.
    yesterday = now_kst - timedelta(days=1)

    # KOBIS API가 요구하는 YYYYMMDD 형식으로 변환합니다.
    return yesterday.strftime("%Y%m%d")


# ---------------------------------------------------------
# KOBIS API 호출
# ---------------------------------------------------------

@st.cache_data(ttl=60 * 30)
def get_boxoffice(target_date):
    """
    KOBIS API에서 특정 날짜의 일일 박스오피스를 가져옵니다.

    반환값:
        영화 목록(list), 오류 메시지(None이면 오류 없음)
    """

    # Streamlit Secrets에서 KOBIS 인증키를 읽습니다.
    # 실제 인증키는 코드에 작성하지 않습니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except (KeyError, FileNotFoundError):
        return None, (
            "KOBIS_KEY를 찾을 수 없습니다. "
            "Streamlit Cloud의 앱 설정 > Secrets에 "
            "KOBIS_KEY가 등록되어 있는지 확인해 주세요."
        )

    # KOBIS에서 요구하는 요청 파라미터입니다.
    params = {
        "key": api_key,
        "targetDt": target_date,
    }

    try:
        # API에 요청합니다.
        response = requests.get(
            API_URL,
            params=params,
            timeout=10,
        )

        # HTTP 상태 코드가 200이 아니면 요청 자체가 실패한 것입니다.
        response.raise_for_status()

        # JSON 응답으로 변환합니다.
        data = response.json()

    except requests.exceptions.Timeout:
        return None, (
            "KOBIS API 요청 시간이 초과되었습니다. "
            "잠시 후 다시 시도하거나 네트워크 상태를 확인해 주세요."
        )

    except requests.exceptions.RequestException as exc:
        return None, (
            "KOBIS API에 연결하지 못했습니다. "
            "인터넷 연결과 KOBIS API 상태를 확인해 주세요.\n\n"
            f"상세 내용: {exc}"
        )

    except json.JSONDecodeError:
        return None, (
            "KOBIS API가 올바른 JSON 응답을 보내지 않았습니다. "
            "KOBIS API가 정상적으로 동작하는지 확인해 주세요."
        )

    # -----------------------------------------------------
    # 중요:
    # KOBIS는 인증키가 잘못되어도 HTTP 200을 반환할 수 있습니다.
    # 이 경우 boxOfficeResult가 아니라 faultInfo가 들어옵니다.
    # -----------------------------------------------------

    if "faultInfo" in data:
        fault_info = data.get("faultInfo", {})

        # KOBIS 오류 메시지의 필드 이름은 상황에 따라 다를 수 있으므로
        # 여러 후보를 확인합니다.
        error_code = (
            fault_info.get("resultCode")
            or fault_info.get("faultCode")
            or "알 수 없음"
        )

        error_message = (
            fault_info.get("resultMsg")
            or fault_info.get("faultString")
            or "KOBIS API에서 오류가 반환되었습니다."
        )

        return None, (
            "KOBIS API에서 오류를 반환했습니다.\n\n"
            f"- 오류 코드: {error_code}\n"
            f"- 오류 내용: {error_message}\n\n"
            "인증키(KOBIS_KEY)가 정확한지, "
            "KOBIS Open API 사용 설정이 정상인지 확인해 주세요."
        )

    # 정상 응답에서 boxOfficeResult를 가져옵니다.
    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return None, (
            "KOBIS 응답에 boxOfficeResult가 없습니다. "
            "API 응답 형식이나 KOBIS 서비스 상태를 확인해 주세요."
        )

    # 영화 목록을 가져옵니다.
    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    if not movie_list:
        return None, (
            "해당 날짜의 영화 목록이 비어 있습니다.\n\n"
            "다음 사항을 확인해 주세요.\n"
            "- 조회 날짜가 정상인지 확인하세요.\n"
            "- KOBIS 일일 박스오피스 데이터가 집계되었는지 확인하세요.\n"
            "- KOBIS API 서비스 상태를 확인하세요."
        )

    return movie_list, None


# ---------------------------------------------------------
# 숫자 변환 함수
# ---------------------------------------------------------

def to_int(value):
    """KOBIS가 문자열로 보내는 숫자를 정수로 변환합니다."""

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def format_number(value):
    """숫자를 천 단위 쉼표가 있는 문자열로 표시합니다."""

    return f"{to_int(value):,}"


# ---------------------------------------------------------
# 화면 제목
# ---------------------------------------------------------

yesterday = get_yesterday_kst()

st.title("🎬 어제의 박스오피스")
st.caption(
    f"한국 시간 기준 {yesterday[:4]}년 "
    f"{yesterday[4:6]}월 {yesterday[6:]}일 "
    "KOBIS 일일 박스오피스"
)


# ---------------------------------------------------------
# 데이터 가져오기
# ---------------------------------------------------------

with st.spinner("KOBIS에서 어제의 박스오피스 데이터를 가져오는 중입니다..."):
    movies, error_message = get_boxoffice(yesterday)


# 오류가 있으면 빈 화면으로 끝내지 않고
# 사용자가 무엇을 확인해야 하는지 안내합니다.
if error_message:
    st.error("박스오피스 데이터를 가져오지 못했습니다.")

    st.warning(error_message)

    st.info(
        "확인 순서: "
        "① Streamlit Cloud Secrets의 KOBIS_KEY → "
        "② KOBIS API 키 상태 → "
        "③ KOBIS API 서비스 상태 → "
        "④ 잠시 후 새로고침"
    )

    st.stop()


# ---------------------------------------------------------
# 데이터프레임 만들기
# ---------------------------------------------------------

df = pd.DataFrame(movies)

# KOBIS의 숫자 필드는 문자열로 오므로 숫자로 변환합니다.
numeric_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt",
]

for column in numeric_columns:
    if column in df.columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        ).fillna(0).astype(int)


# 순위 기준으로 다시 정렬합니다.
df = df.sort_values("rank").reset_index(drop=True)


# 혹시 API 응답은 성공했지만 영화 데이터가 비어 있는 경우를
# 한 번 더 방어합니다.
if df.empty:
    st.warning(
        "KOBIS에서 영화 목록이 비어 있는 응답을 받았습니다. "
        "KOBIS 데이터가 정상적으로 집계되었는지 확인해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# 1위 영화
# ---------------------------------------------------------

first_movie = df.iloc[0]

st.subheader(f"🥇 1위 — {first_movie['movieNm']}")


# 1위 영화의 핵심 지표 세 개를 크게 보여줍니다.
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="어제 관객수",
        value=f"{format_number(first_movie['audiCnt'])}명",
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{format_number(first_movie['audiAcc'])}명",
    )

with col3:
    st.metric(
        label="스크린수",
        value=f"{format_number(first_movie['scrnCnt'])}개",
    )


# ---------------------------------------------------------
# 관객수 상위 5편 막대그래프
# ---------------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values("audiCnt", ascending=False)
    .head(5)
    .copy()
)

# 영화명을 인덱스로 사용하면 Streamlit의 기본 막대그래프에서
# 영화별 관객수를 쉽게 비교할 수 있습니다.
chart_data = top5.set_index("movieNm")[["audiCnt"]]

st.bar_chart(
    chart_data,
    x_label="영화",
    y_label="관객수",
)


# ---------------------------------------------------------
# 전체 박스오피스 표
# ---------------------------------------------------------

st.subheader("🎞️ 전체 박스오피스")

# 사용자에게 보여줄 컬럼만 골라서 새 데이터프레임을 만듭니다.
display_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt",
    ]
].copy()


# 화면에 표시할 한국어 컬럼명을 지정합니다.
display_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
]


# 숫자 컬럼은 천 단위 쉼표가 들어가도록 표시합니다.
display_df["관객수"] = display_df["관객수"].map(
    lambda x: f"{x:,}"
)

display_df["누적관객"] = display_df["누적관객"].map(
    lambda x: f"{x:,}"
)

display_df["스크린수"] = display_df["스크린수"].map(
    lambda x: f"{x:,}"
)


# Streamlit 표로 보여줍니다.
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------
# 데이터 기준 안내
# ---------------------------------------------------------

st.caption(
    f"※ 조회 기준일: {yesterday} (한국 시간) · "
    "출처: 영화관입장권통합전산망(KOBIS)"
)
    "출처: 영화관입장권통합전산망(KOBIS)"
)
