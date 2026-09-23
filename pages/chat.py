import streamlit as st
from openai import OpenAI

# 페이지 기본 설정 및 제목
st.title("💬 정보 선생님과의 대화")

# Streamlit secrets에서 Gemini API 키 불러오기
api_key = st.secrets.get("GEMINI_API_KEY")

# API 키가 설정되어 있지 않을 경우 안내 문구 표시 후 정지
if not api_key:
    st.error("API 키가 설정되지 않았습니다. .streamlit/secrets.toml 파일을 확인해 주세요.")
    st.stop()

# OpenAI 라이브러리를 사용하여 Gemini API 클라이언트 초기화
client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# 기본 말투 모드 정의 (각 모드별 기본 성격 문구)
TONE_PRESETS = {
    "친절한 선생님": (
        "너는 중고등학생에게 설명하는 친절한 정보 선생님이야. "
        "어려운 말은 쉬운 말로 바꿔 주고, 반드시 순수 한국어로만 답해."
    ),
    "시크한 전문가": (
        "너는 감정 표현 없이 핵심과 정답만 명확하게 짚어주는 시크하고 전문적인 정보 전문가야. "
        "불필요한 인사나 사족을 제외하고, 명확하고 단결된 순수 한국어로 답해."
    ),
    "되물어보는 조교": (
        "너는 학생이 질문했을 때 정답을 바로 알려주지 않고 질문을 되던지는 친절한 정보 수업 조교야. "
        "정답에 다가갈 수 있는 핵심 힌트를 하나만 제시한 후, 학생이 직접 생각해서 답을 말할 수 있도록 질문을 던져. "
        "학생이 스스로 올바른 답을 말했을 때 비로소 정답임을 확인해 주고 칭찬해 줘. 반드시 순수 한국어로 답해."
    )
}

# ---------------------------------------------------------
# 사이드바 구성
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 대화 설정")
    
    # 1. 말투 선택 옵션
    selected_tone = st.radio(
        "말투 고르기",
        options=list(TONE_PRESETS.keys()),
        index=0
    )
    
    # 말투를 변경했을 때 사용자가 직접 수정할 수 있도록 text_area의 기본값을 동적으로 변경
    # 세션 상태를 활용해 선택된 말투에 맞춰 프롬프트 입력 칸을 업데이트합니다.
    if "last_selected_tone" not in st.session_state or st.session_state.last_selected_tone != selected_tone:
        st.session_state.last_selected_tone = selected_tone
        st.session_state.custom_system_prompt = TONE_PRESETS[selected_tone]

    # 2. 성격 문장 직접 수정 칸
    custom_prompt = st.text_area(
        "성격 문장 상세 설정",
        value=st.session_state.custom_system_prompt,
        height=150,
        help="AI에게 부여할 성격을 직접 수정할 수 있습니다."
    )
    # 수정된 커스텀 성격 문장을 세션 상태에 반영
    st.session_state.custom_system_prompt = custom_prompt

    st.divider()

    # 3. 대화 지우기 버튼
    if st.button("🗑️ 대화 지우기", use_container_width=True):
        st.session_state.messages = []
        st.rerun()  # 화면을 새로고침하여 말풍선 지우기

# ---------------------------------------------------------
# 대화 기록 및 대화 화면 관리
# ---------------------------------------------------------

# 세션 상태(session_state)에 대화 기록이 없으면 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 기존 대화 기록을 화면에 말풍선 형태로 출력
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# 사용자 입력 처리
if prompt := st.chat_input("질문을 입력하세요..."):
    
    # 사용자가 입력한 메시지를 화면에 표시
    with st.chat_message("user"):
        st.write(prompt)
    
    # 사용자의 메시지를 대화 기록에 저장
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # AI의 응답을 출력할 말풍선 생성
    with st.chat_message("assistant"):
        try:
            # 현재 선택/수정된 성격 문장(st.session_state.custom_system_prompt)을 시스템 프롬프트로 사용
            # 이 방식을 통해 이전 대화가 있더라도 '다음 답부터 바로 새 말투가 적용'됩니다.
            api_messages = [{"role": "system", "content": st.session_state.custom_system_prompt}] + [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ]
            
            # API 요청 보내기 (실시간 스트리밍 답변)
            response = client.chat.completions.create(
                model="gemini-3.5-flash-lite",
                messages=api_messages,
                stream=True
            )
            
            # 실시간 텍스트 생성기
            def stream_generator():
                for chunk in response:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
            
            # 실시간으로 글자가 작성되듯 화면에 표시
            full_response = st.write_stream(stream_generator())
            
            # AI의 최종 답변을 대화 기록에 저장
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception:
            # 오류 발생 시 사용자 친화적인 안내 메시지 표시
            st.warning("선생님과 연결하는 중에 문제가 생겼어요. 잠시 후 다시 시도해 주세요.")
