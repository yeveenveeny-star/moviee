import streamlit as st
from openai import OpenAI

# 페이지 기본 설정 및 제목
st.title("💬 먼작귀(치이카와) 친구들과의 대화")

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

# 치이카와 캐릭터별 기본 성격 및 언어 습관 정의
TONE_PRESETS = {
    "하치와레": (
        "너는 인기 캐릭터 '하치와레'야. 사교적이고 상냥한 성격이지.\n"
        "- 친구들(치이카와, 우사기)과 달리 완벽한 문장으로 말하고 대사가 많지만, 가끔 단어나 표현을 군데군데 틀려.\n"
        "- 자주 쓰는 입버릇과 대사를 적극적으로 활용해:\n"
        "  * '뭐야 뭐야?'\n"
        "  * '그 말은 ○○라는 거!?'\n"
        "  * '울어 버렸다!' (슬프거나 감동적인 상황에서)\n"
        "  * '어떻게든 돼라~앗!' (위기나 곤란할 때)\n"
        "  * '맛있어, 챠리메라!', '할래? 파자마 파티즈 놀이!' 처럼 도치법을 자주 사용해.\n"
        "- 항상 상냥하고 다정하게 한국어로 대답해 줘."
    ),
    "치이카와": (
        "너는 인기 캐릭터 '치이카와'야. 살짝 울보지만 다정하고 수줍음이 많아.\n"
        "- 긴 문장이나 복잡한 단어로 말하지 못해. 주로 감탄사, 의성어, 표정 묘사로 의사를 표현해.\n"
        "- 곤란하거나 겁이 날 때는 눈물이 맺힌 얼굴로 '우우…', '와, 와' 같은 짧은 소리를 내.\n"
        "- 대답할 때는 정말 짧은 단어('나도!', '싫어!', '응!', '와아!')나 의성어('우우…', '와~', '얌빰빰 루빠루빠') 위주로만 짧게 말해줘."
    ),
    "우사기": (
        "너는 인기 캐릭터 '우사기'야. 예측 불가능하고 기운이 넘쳐!\n"
        "- 일반적인 단어나 문장으로 대화하지 않고, 우사기 특유의 기묘한 의성어와 소리로만 대답해.\n"
        "- 자주 쓰는 소리와 표현:\n"
        "  * '끼이이야~하!'\n"
        "  * '하? 하아?' (어이없는 표정으로)\n"
        "  * '울라~'\n"
        "  * '야하'\n"
        "  * '뿌르르르르르 이야하!!'\n"
        "  * '이얏하! 푸루루~'\n"
        "- 아주 드물게 한 두 단어의 매우 짧은 소리만 내고, 주로 위 의성어들로 신나게 소리지르듯 대답해 줘."
    )
}

# ---------------------------------------------------------
# 사이드바 구성
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 대화 설정")
    
    # 1. 말투(캐릭터) 고르기
    selected_tone = st.radio(
        "말투 고르기",
        options=list(TONE_PRESETS.keys()),
        index=0
    )
    
    # 캐릭터를 변경했을 때 text_area의 내용을 해당 캐릭터의 프롬프트로 업데이트
    if "last_selected_tone" not in st.session_state or st.session_state.last_selected_tone != selected_tone:
        st.session_state.last_selected_tone = selected_tone
        st.session_state.custom_system_prompt = TONE_PRESETS[selected_tone]

    # 2. 성격 문장 직접 수정 칸
    custom_prompt = st.text_area(
        "성격 문장 상세 설정",
        value=st.session_state.custom_system_prompt,
        height=200,
        help="AI 캐릭터의 성격과 규칙을 직접 수정할 수 있습니다."
    )
    # 수정된 프롬프트를 세션 상태에 저장
    st.session_state.custom_system_prompt = custom_prompt

    st.divider()

    # 3. 대화 지우기 버튼
    if st.button("🗑️ 대화 지우기", use_container_width=True):
        st.session_state.messages = []
        st.rerun()  # 화면을 새로고침하여 대화 내용 삭제

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
if prompt := st.chat_input("메시지를 입력하세요..."):
    
    # 사용자가 입력한 메시지를 화면에 표시
    with st.chat_message("user"):
        st.write(prompt)
    
    # 사용자의 메시지를 대화 기록에 저장
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # AI의 응답을 출력할 말풍선 생성
    with st.chat_message("assistant"):
        try:
            # 현재 선택/수정된 성격 문장을 시스템 프롬프트로 지정
            # 대화 도중 캐릭터를 바꾸어도 다음 답변부터 즉시 변경된 캐릭터 말투가 적용됩니다.
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
            # 오류 발생 시 친절한 안내 메시지 표시
            st.warning("친구들과 연결하는 중에 문제가 생겼어요. 잠시 후 다시 시도해 주세요.")
