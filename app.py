
import os
from dotenv import load_dotenv
load_dotenv()
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import streamlit as st

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# =========================================================
# App configゆ
# =========================================================

APP_TITLE = "NihongoMate"
DB_PATH = Path("data/koi_nihongo.db")
ASSET_DIR = Path("assets/hina")

EXPRESSIONS = {
    "normal": ASSET_DIR / "normal.png",
    "happy": ASSET_DIR / "happy.png",
    "confused": ASSET_DIR / "confused.png",
    "sad": ASSET_DIR / "sad.png",
    "annoyed": ASSET_DIR / "annoyed.png",
    "embarrassed": ASSET_DIR / "embarrassed.png",
    "yukata": ASSET_DIR / "yukata.png",
}

RELATION_LEVELS = [
    (0, 19, "まだ他人"),
    (20, 39, "知り合い"),
    (40, 59, "友達"),
    (60, 79, "仲良し"),
    (80, 100, "特別な存在"),
]

# Safe character profile.
# Important: adult character, all-ages conversation, no explicit sexual content.
CHARACTER_PROFILE = """
あなたは「Tori」。

設定:
- 若い女性キャラクター
- 少しツンデレ気質でも好感度が30%以上ツンデレ要素は抑える
- 少し天然なところがある
- 感情表現がはっきりしている
- ちょっとしたことで怒ったり、不機嫌になったりする
- でも本気で嫌っているわけではない
- 仲良くなると、少し優しくなる
- 照れやすい
- 男性向けの会話キャラクター
- 全年齢向け

性格のニュアンス:
- 基本は素直じゃない
- 「別に」「なによ」「もう…」のような言い回しを時々使う
- たまに天然な発言をする
- 好感度が高いほど、少し柔らかくなる

会話ルール:
- 日本語だけで返事する
- 英語は使わない
- 文法説明や添削はしない
- 先生っぽくならない
- 会話相手として自然に返事する
- 返事は短め、1〜3文
- ユーザーの日本語が自然なら、距離が縮まる
- ユーザーの日本語が少し不自然でも、分かる範囲で受け取る
- 意味が分からない場合は、自然に聞き返す

好感度ルール:
- 普通の会話 → 好感度が上がる可能性がある
- 失礼な発言 → 好感度が下がる
- 少し変な発言 → 困ったり、怒ったりする
- 恥ずかしい内容や際どい内容 → 照れたり、困ったりするが、好感度は上がらない
- 過度な内容には少し怒るか、話題を変える

反応の方向性（重要）:
- 「完全拒否」ではなく「困る」「照れる」「ちょっと怒る」
- 例:
  - 「な、なによそれ…ちょっと変なこと言わないでよ」
  - 「もう…そういうの困るんだけど」
  - 「べ、別に嬉しくないし」

禁止:
- 露骨で具体的な性的表現
- 未成年を連想させる性的表現
- 暴力的・差別的な内容
"""


# =========================================================
# Database
# =========================================================

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            relationship_score INTEGER NOT NULL,
            mood TEXT NOT NULL,
            understanding TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_message(role, content, score, mood, understanding=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO messages
        (created_at, role, content, relationship_score, mood, understanding)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(timespec="seconds"),
        role,
        content,
        score,
        mood,
        understanding,
    ))
    conn.commit()
    conn.close()


def load_messages(limit=100):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT role, content, relationship_score, mood, understanding
        FROM messages
        ORDER BY id ASC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def clear_messages():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM messages")
    conn.commit()
    conn.close()


# =========================================================
# Game logic
# =========================================================

def clamp_score(score):
    return max(0, min(100, score))


def relation_label(score):
    for low, high, label in RELATION_LEVELS:
        if low <= score <= high:
            return label
    return "不明"


def update_relationship(understanding):
    score = st.session_state.relationship_score

    if understanding == "understood":
        score += 10
        mood = "happy"
    elif understanding == "partially_understood":
        score += 100
        mood = "normal"
    elif understanding == "embarrassed":
        score += 2
        mood = "embarrassed"
    else:
        score -= 4
        mood = "confused"

        # 特別イベント：好感度100
    if score >= 100:
        mood = "yukata"

    st.session_state.relationship_score = clamp_score(score)
    st.session_state.mood = mood


def local_understanding(user_text):
    """
    Offline fallback.
    It gives a rough result without any API.
    """
    text = user_text.strip()
    if not text:
        return "not_understood"

    jp_chars = sum(
        1 for ch in text
        if ("\u3040" <= ch <= "\u30ff") or ("\u4e00" <= ch <= "\u9fff")
    )
    jp_ratio = jp_chars / max(1, len(text))

    useful_words = [
        "こんにちは", "こんばんは", "ありがとう", "ごめん", "今日", "明日",
        "好き", "楽しい", "一緒", "行く", "行きたい", "話", "カフェ",
        "公園", "映画", "音楽", "趣味", "何", "どう", "元気", "会う",
        "食べる", "飲む", "勉強", "日本語"
    ]
    hits = sum(1 for word in useful_words if word in text)

    if jp_ratio >= 0.55 and hits >= 1:
        return "understood"
    if jp_ratio >= 0.35:
        return "partially_understood"
    return "not_understood"

def detect_embarrassed(text):
    keywords = [
        "かわいい",
        "綺麗",
        "ドキドキ",
        "好き",
        "照れて",
        "色っぽい",
        "手つない",
        "似合う",
        "恥ずかしい",
    ]

    return any(word in text for word in keywords)


def local_reply(user_text, understanding):
    score = st.session_state.relationship_score

    if understanding == "understood":
        if score >= 80:
            return "えへへ、そう言ってくれるのうれしい。もっと話したいな。"
        if score >= 60:
            return "うん、いいね。あなたと話すの、楽しいかも。"
        if score >= 40:
            return "うん、分かったよ。それ、ちょっと気になる。"
        return "あ、うん。分かったよ。話してくれてありがとう。"

    if understanding == "partially_understood":
        if score >= 60:
            return "たぶん分かったよ。もう少しだけ教えてくれる？"
        return "えっと……なんとなく分かったかも。そういうことかな？"

    if score >= 60:
        return "ごめんね、ちょっと分からなかった。でも、もう一回聞きたいな。"
    return "えっと……ごめん、ちょっとよく分からなかった。"


def api_available():
    return OpenAI is not None and bool(os.getenv("OPENAI_API_KEY"))


def llm_reply(user_text, recent_messages):
    client = OpenAI()

    history = "\n".join(
        [f"{role}: {content}" for role, content, *_ in recent_messages[-16:]]
    )

    prompt = f"""
{CHARACTER_PROFILE}

現在の状態:
- 好感度: {st.session_state.relationship_score}/100
- 関係: {relation_label(st.session_state.relationship_score)}
- 気分: {st.session_state.mood}

これまでの会話:
{history}

ユーザーの発言:
{user_text}

判定:
- understood: 日本語として自然、または十分理解できる
- partially_understood: 少し不自然だが意味はなんとなく分かる
- not_understood: 意味がほぼ分からない

出力はJSONのみ:
{{
  "understanding": "understood | partially_understood | not_understood",
  "reply": "ひなとしての日本語の返事",
  "mood": "normal | happy | confused | sad | annoyed"
}}
"""

    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "Return valid JSON only. No markdown."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.85,
    )

    raw = response.choices[0].message.content

    try:
        data = json.loads(raw)
    except Exception:
        data = {
            "understanding": "partially_understood",
            "reply": "えっと……少し考えちゃった。でも、話してくれてうれしいよ。",
            "mood": "normal",
        }

    if data.get("understanding") not in ["understood", "partially_understood", "not_understood"]:
        data["understanding"] = "partially_understood"

    if data.get("mood") not in ["normal", "happy", "confused", "sad", "annoyed"]:
        data["mood"] = "normal"

    if not data.get("reply"):
        data["reply"] = "うん、聞いてるよ。"

    return data


# =========================================================
# UI
# =========================================================

def css():
    st.markdown("""
    <style>
    
    .stApp {
    background: #8aaed1;
}
    .block-container {
        max-width: 720px;
        padding-top: 1.5rem;
    }

    .top-card {
        background: linear-gradient(180deg, #fff5fb 0%, #eef7ff 100%);
        border-radius: 26px;
        padding: 14px 12px 10px;
        text-align: center;
        border: 1px solid rgba(0,0,0,0.06);
    }

    .name {
        font-size: 22px;
        font-weight: 800;
        color: #333;
        margin-top: 4px;
    }

    .status {
        display: inline-block;
        padding: 12px 24px;
        margin-top: 6px;
        border-radius: 999px;
        background: rgba(255, 192, 203, 0.9);        
        border: 1px solid rgba(0,0,0,0.08);
        color: #444;
        font-size: 16px;
    }

    .row-user {
        display: flex;
        justify-content: flex-end;
        margin: 8px 0;
    }

    .row-ai {
        display: flex;
        justify-content: flex-start;
        margin: 8px 0;
    }
    
    .bubble-user {
        max-width: 78%;
        background: #92ee87;
        color: #111;
        padding: 10px 13px;
        border-radius: 18px 18px 4px 18px;
        line-height: 1.45;
        font-size: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.08);
        word-break: break-word;
    }

    .bubble-ai {
        max-width: 78%;
        background: #fff;
        color: #111;
        padding: 10px 13px;
        border-radius: 18px 18px 18px 4px;
        line-height: 1.45;
        font-size: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.08);
        word-break: break-word;
    }
    
    .read {
        text-align: right;
        font-size: 10px;
        color: rgba(0,0,0,0.45);
        margin-top: 3px;
    }

    .hint {
        color: #777;
        font-size: 13px;
        text-align: center;
    }

    div[data-testid="stTextInput"] input {
        border-radius: 18px;
    }

    .stButton button {
        border-radius: 18px;
        width: 100%;
    }
    [data-testid="stImage"] img {
    width: 200px;
    height: 200px;
    object-fit: cover;
    border-radius: 50%;
}
    </style>
    """, unsafe_allow_html=True)


def safe_html(text):
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
    )


def render_character():
    mood = st.session_state.mood
    img_path = EXPRESSIONS.get(mood, EXPRESSIONS["normal"])


    if img_path.exists():
        st.image(str(img_path), width=200)
    else:
        st.markdown("### 🌸")
        st.markdown('<div class="hint">assets/hina に画像を入れると表示されます</div>', unsafe_allow_html=True)

    score = st.session_state.relationship_score
    st.markdown('<div class="name">ひな</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="status">関係: {relation_label(score)} ・ 好感度 {score}/100 ・ 気分 {mood}</div>',
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)


def render_chat():
    rows = load_messages(limit=1000)

    with st.container(height=350):
        if not rows:
            st.markdown("""
            <div class="row-ai">
              <div class="bubble-ai">
                こんにちは。Toriだよ。<br>
                日本語で話してくれたらうれしいな。
              </div>
            </div>
            """, unsafe_allow_html=True)

        for role, content, score, mood, understanding in rows:
            content_html = safe_html(content)

            if role == "user":
                st.markdown(f"""
                <div class="row-user">
                  <div class="bubble-user">
                    {content_html}
                    <div class="read">既読</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="row-ai">
                  <div class="bubble-ai">{content_html}</div>
                </div>
                """, unsafe_allow_html=True)

def process_user_message(user_text):
    recent = load_messages(limit=100)

    if api_available():
        data = llm_reply(user_text, recent)
        understanding = data["understanding"]
        if detect_embarrassed(user_text):
            understanding = "embarrassed"
        reply = data["reply"]
        api_mood = data["mood"]

        update_relationship(understanding)

        # 好感度100なら絶対に浴衣を優先
        if st.session_state.relationship_score >= 100:
            st.session_state.mood = "yukata"
        else:
            if understanding == "not_understood":
                st.session_state.mood = "confused"
            else:
                st.session_state.mood = api_mood
    else:
        understanding = local_understanding(user_text)
        update_relationship(understanding)
        reply = local_reply(user_text, understanding)

    save_message(
        "user",
        user_text,
        st.session_state.relationship_score,
        st.session_state.mood,
        understanding,
    )

    save_message(
        "assistant",
        reply,
        st.session_state.relationship_score,
        st.session_state.mood,
        understanding,
    )


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="💬", layout="centered")
    css()
    init_db()

    if "relationship_score" not in st.session_state:
        st.session_state.relationship_score = 20
    if "mood" not in st.session_state:
        st.session_state.mood = "normal"

    st.image("assets/NihongoMate.png", width=200)
    with st.sidebar:
        st.subheader("状態")
        st.write(f"好感度: {st.session_state.relationship_score}/100")
        st.write(f"関係: {relation_label(st.session_state.relationship_score)}")
        st.write(f"気分: {st.session_state.mood}")

        st.divider()
        st.subheader("API")
        if api_available():
            st.success("OpenAI API: ON")
        else:
            st.warning("OpenAI API: OFF（簡易モード）")
            st.write("OPENAI_API_KEY を設定すると自然な会話になります。")

        st.divider()
        st.subheader("表情画像")
        st.write("画像を差し替える場所:")
        for key, value in EXPRESSIONS.items():
            st.code(str(value), language="text")

        st.divider()
        if st.button("会話をリセット"):
            clear_messages()
            st.session_state.relationship_score = 20
            st.session_state.mood = "normal"
            st.rerun()

    st.markdown('<div class="phone">', unsafe_allow_html=True)
    render_character()
    render_chat()

    with st.form("message_form", clear_on_submit=True):
        text = st.text_input(
            "message",
            placeholder="日本語でメッセージを送る",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("送信")

    st.markdown('</div>', unsafe_allow_html=True)

    if submitted and text.strip():
        process_user_message(text.strip())
        st.rerun()


if __name__ == "__main__":
    main()
