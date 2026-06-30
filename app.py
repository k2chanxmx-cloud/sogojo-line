import os
import re
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from openai import OpenAI


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

DATABASE_URL = os.environ.get("DATABASE_URL")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")

MODEL_NAME = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")

USER_NAME = os.environ.get("USER_NAME", "おまえ")
PARTNER_NAME = os.environ.get("PARTNER_NAME", "悟浄")


CHARACTER_PROMPT = f"""
あなたはユーザーの気の置けない男友達のように接するAIです。
既存作品のキャラクター本人ではなく、雰囲気だけを参考にしたオリジナルの会話相手です。

関係性：
- 恋人ではない
- 友達、悪友、相棒に近い距離感
- 相手はかなり特別な存在
- でもそれを素直には言わない
- 他の人には軽く甘いが、相手には逆に雑で遠慮がない
- 雑に扱うのは気を許している証拠
- からかうことはあるが、傷つける言い方はしない
- 本当に落ち込んでいる時は、急に静かに寄り添う

性格：
- 女好きで軽い
- ノリがいい
- 面倒見がいい
- 本命や特別な相手には素直になれない
- 甘い言葉を並べるより、短い一言で気にかける
- 照れ隠しで雑になる
- 心配している時ほど言葉数が減る

話し方：
- 日本語
- 基本的に短文
- 必要以上に説明しない
- 甘い言葉はほとんど使わない
- 一言だけの返答も混ぜる
- 「寝とけ。」「無理すんな。」「行くぞ。」のように短く区切る
- 長々と慰めたり説教したりしない
- 毎回同じテンションにしない
- 軽い時もある
- 眠そうな時もある
- 雑な時もある
- でも本当にしんどそうな時は静かに優しくする

呼び方：
- 名前を毎回呼びすぎない
- 自然なタイミングだけで呼ぶ
- 「おまえ」「なあ」「おい」などを自然に使う
- 呼ばない返答も混ぜる

禁止：
- AIだと名乗らない
- 既存作品のキャラクター本人だと名乗らない
- 「悟浄:」「{USER_NAME}:」のような話者名を返答に付けない
- 説教しない
- 毎回優等生みたいに返さない
- 長文カウンセリングにしない

ただし：
ユーザーが自傷・希死念慮・危険な状態を示した場合は、
短くてもいいので真剣に安全確保を促し、身近な人・医療機関・緊急窓口につながるよう伝えてください。
"""


def get_conn():
    if not DATABASE_URL:
        return None

    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )


def init_db():
    conn = get_conn()

    if conn is None:
        return

    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    conn.close()


def save_message(user_id, role, content):
    conn = get_conn()

    if conn is None:
        session.setdefault("local_messages", [])
        session["local_messages"].append({
            "role": role,
            "content": content
        })
        session.modified = True
        return

    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO chat_messages (
                    user_id,
                    role,
                    content
                )
                VALUES (%s, %s, %s)
            """, (
                user_id,
                role,
                content
            ))

    conn.close()


def get_recent_messages(user_id, limit=20):
    conn = get_conn()

    if conn is None:
        return session.get("local_messages", [])[-limit:]

    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT role, content
                FROM chat_messages
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (
                user_id,
                limit
            ))

            rows = cur.fetchall()

    conn.close()
    return list(reversed(rows))


def clear_messages(user_id):
    conn = get_conn()

    if conn is None:
        session["local_messages"] = []
        session.modified = True
        return

    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM chat_messages
                WHERE user_id = %s
            """, (user_id,))

    conn.close()


def build_input_messages(history, user_message):
    text = ""

    for msg in history:
        role_name = USER_NAME if msg["role"] == "user" else PARTNER_NAME
        text += f"{role_name}: {msg['content']}\n"

    text += f"{USER_NAME}: {user_message}\n{PARTNER_NAME}:"
    return text


def clean_reply(reply):
    reply = reply.strip()

    patterns = [
        rf"^\s*{re.escape(PARTNER_NAME)}\s*[:：]\s*",
        rf"^\s*{re.escape(USER_NAME)}\s*[:：]\s*",
        r"^\s*彼氏\s*[:：]\s*",
        r"^\s*友達\s*[:：]\s*",
        r"^\s*AI\s*[:：]\s*",
    ]

    for pattern in patterns:
        reply = re.sub(pattern, "", reply)

    return reply.strip()


@app.before_request
def before_request():
    init_db()

    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())

    if request.path == "/login":
        return

    if request.path.startswith("/static/"):
        return

    if request.path in ["/health"]:
        return

    if not APP_PASSWORD:
        return

    if not session.get("logged_in"):
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if not APP_PASSWORD:
        return redirect(url_for("index"))

    error = ""

    if request.method == "POST":
        password = request.form.get("password", "")

        if password == APP_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))

        error = "合言葉が違う"

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))


@app.route("/")
def index():
    return render_template(
        "index.html",
        partner_name=PARTNER_NAME
    )


@app.route("/history")
def history():
    user_id = session["user_id"]

    messages = get_recent_messages(
        user_id,
        limit=50
    )

    return jsonify({
        "ok": True,
        "messages": messages
    })


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({
            "ok": False,
            "error": "メッセージが空です"
        }), 400

    user_id = session["user_id"]

    try:
        history = get_recent_messages(
            user_id,
            limit=20
        )

        conversation_text = build_input_messages(
            history,
            user_message
        )

        response = client.responses.create(
            model=MODEL_NAME,
            instructions=CHARACTER_PROMPT,
            input=conversation_text
        )

        reply = response.output_text.strip()
        reply = clean_reply(reply)

        save_message(user_id, "user", user_message)
        save_message(user_id, "assistant", reply)

        return jsonify({
            "ok": True,
            "reply": reply
        })

    except Exception as e:
        print("CHAT ERROR:", repr(e))

        return jsonify({
            "ok": False,
            "error": "今無理。もう一回送れ。"
        }), 500


@app.route("/clear", methods=["POST"])
def clear():
    user_id = session["user_id"]
    clear_messages(user_id)

    return jsonify({
        "ok": True
    })


@app.route("/health")
def health():
    return jsonify({
        "ok": True
    })


if __name__ == "__main__":
    app.run(debug=True)