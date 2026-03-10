from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from functools import wraps
from datetime import datetime
from db import get_db, close_db, init_db
from flask_mail import Mail, Message
from dotenv import load_dotenv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)
app.secret_key = "dev-secret-change-me"

MAIL_USERNAME = os.getenv("MAIL_USERNAME", "").strip()
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "").strip()
MAIL_TO = os.getenv("MAIL_TO", "2co2co0417@gmail.com").strip()

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = MAIL_USERNAME
app.config["MAIL_PASSWORD"] = MAIL_PASSWORD
app.config["MAIL_DEFAULT_SENDER"] = MAIL_USERNAME

mail = Mail(app)

print("BASE_DIR =", BASE_DIR)
print(".env exists =", os.path.exists(os.path.join(BASE_DIR, ".env")))
print("MAIL_USERNAME =", repr(MAIL_USERNAME))
print("MAIL_TO =", repr(MAIL_TO))
print("MAIL_DEFAULT_SENDER =", repr(app.config["MAIL_DEFAULT_SENDER"]))

# テンプレート・静的ファイルのキャッシュを極力止める
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.jinja_env.auto_reload = True

init_db(app)
app.teardown_appcontext(close_db)

print("APP FILE:", __file__)
print("CWD:", os.getcwd())
print("ROOT:", app.root_path)
print("TEMPLATE DIR:", os.path.join(app.root_path, "templates"))
print("INDEX EXISTS:", os.path.exists(os.path.join(app.root_path, "templates", "index.html")))
print("DASHBOARD EXISTS:", os.path.exists(os.path.join(app.root_path, "templates", "dashboard.html")))
print("SIDEBAR EXISTS:", os.path.exists(os.path.join(app.root_path, "templates", "_right_sidebar.html")))
print("STATIC CSS:", os.path.join(app.root_path, "static", "css", "style.css"))
print("CSS EXISTS:", os.path.exists(os.path.join(app.root_path, "static", "css", "style.css")))


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# --- モック：ログイン用（本番はDB/取引先マスタに置き換え） ---
DEMO_USER = {
    "phone": "09000000000",   # 仮
    "password": "1234",       # 仮
    "company": "○○建設",
    "name": "田中様"
}

# --- モック：お知らせ（本番はDBへ） ---
NEWS = [
    {
        "id": 1,
        "title": "ゴールデンウィーク休業日のお知らせ",
        "date": "2026-03-09",
        "body": "（モック）休業日はカレンダーをご確認ください。"
    },
    {
        "id": 2,
        "title": "アルバイト募集のお知らせ",
        "date": "2026-03-10",
        "body": "（モック）現在アルバイトを募集しています。"
    },
]

ORDER_PHONE = "0898-48-1805"


# -----------------------------
# ログイン必須デコレータ
# -----------------------------
def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


# -----------------------------
# お知らせ取得（モック版）
# -----------------------------
def get_news_list(limit=3):
    sorted_news = sorted(NEWS, key=lambda x: (x["date"], x["id"]), reverse=True)
    return sorted_news[:limit]


def get_news_all():
    return sorted(NEWS, key=lambda x: (x["date"], x["id"]), reverse=True)


def get_news_item(news_id):
    return next((n for n in NEWS if n["id"] == news_id), None)


# -----------------------------
# 全テンプレート共通データ
# -----------------------------
@app.context_processor
def inject_common():
    now = datetime.now()

    # 簡易営業ステータス
    if now.weekday() == 6:   # 日曜
        status = "本日休業日"
    else:
        status = "本日営業中　8:00〜17:00"

    return {
        "business_status": status,
        "order_phone": ORDER_PHONE,
        "now_year": now.year,
        "news": get_news_list(3)
    }


# --- 公開 ---
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        company = request.form.get("company", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()

        if not company or not name or not email or not message:
            flash("会社名・お名前・メールアドレス・お問い合わせ内容を入力してください。", "error")
            return redirect(url_for("contact"))

        to_email = os.getenv("MAIL_TO", "2co2co0417@gmail.com")

        subject = f"【お問い合わせ】{company} {name}様"

        body = f"""株式会社今治生コンのWebサイトからお問い合わせが届きました。

【会社名】
{company}

【お名前】
{name}様

【メールアドレス】
{email}

【お問い合わせ内容】
{message}
"""

        try:
            msg = Message(
                subject=subject,
                recipients=[to_email],
                reply_to=email,
                body=body,
                sender=os.getenv("MAIL_USERNAME", "2co2co0417@gmail.com")
            )
            mail.send(msg)

            flash(f"お問い合わせを受け付けました。{name}様", "ok")
            return redirect(url_for("contact"))

        except Exception as e:
            print("メール送信エラー:", e)
            flash("お問い合わせの送信に失敗しました。メール設定をご確認ください。", "error")
            return redirect(url_for("contact"))

    return render_template("contact.html")


# --- ログイン ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()

        db = get_db()
        user = db.execute(
            "SELECT id, company, name, phone FROM clients WHERE phone = ?",
            (phone,)
        ).fetchone()

        if user:
            session["user"] = {
                "id": user["id"],
                "company": user["company"],
                "name": user["name"],
                "phone": user["phone"]
            }
            next_url = request.args.get("next") or url_for("dashboard")
            return redirect(next_url)

        flash("この電話番号は登録されていません（モック）", "ng")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))

@app.route("/precheck")
def precheck():
    return render_template("precheck.html")

# --- 取引先専用 ---
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/map", methods=["GET", "POST"])
@login_required
def map_send():
    if request.method == "POST":
        # 本番：地図URL/住所→メール送信、履歴保存
        site_name = request.form.get("site_name", "").strip()
        map_url = request.form.get("map_url", "").strip()
        note = request.form.get("note", "").strip()

        flash(
            f"（モック）現場地図を送信しました：{site_name if site_name else '現場名未入力'}",
            "ok"
        )
        return redirect(url_for("map_send"))

    return render_template("map.html")


@app.route("/mix-report", methods=["GET", "POST"])
@login_required
def mix_report():
    if request.method == "POST":
        # 本番：依頼内容→受付→担当へ通知、履歴保存
        project = request.form.get("project", "").strip()
        mix_no = request.form.get("mix_no", "").strip()
        date_needed = request.form.get("date_needed", "").strip()

        flash(
            f"（モック）配合報告書の依頼を受け付けました：{project if project else '工事名未入力'}",
            "ok"
        )
        return redirect(url_for("mix_report"))

    return render_template("mix_report.html")


@app.route("/price")
@login_required
def price():
    # 本番：顧客別価格・適用期間・PDFダウンロードなど
    return render_template("price.html")


@app.route("/news")
@login_required
def news_list():
    return render_template("news_list.html", news=get_news_all())


@app.route("/news/<int:news_id>")
@login_required
def news_detail(news_id: int):
    item = get_news_item(news_id)
    if not item:
        abort(404)
    return render_template("news_detail.html", item=item)


if __name__ == "__main__":
    app.run(debug=True)