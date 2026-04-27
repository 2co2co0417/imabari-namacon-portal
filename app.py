from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_from_directory, make_response
from functools import wraps
from datetime import datetime, date, time, timedelta, timezone
from db import get_db, close_db, init_db
from flask_mail import Mail, Message
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import os
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

JST = timezone(timedelta(hours=9))

def jst_today():
    return datetime.now(JST).date().isoformat()

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = True   # RenderならOK

MAIL_USERNAME = os.getenv("MAIL_USERNAME", "").strip()
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "").strip()
MAIL_TO = os.getenv("MAIL_TO", "2co2co0417@gmail.com").strip()

OWNER_USERNAME = os.getenv("OWNER_USERNAME", "owner").strip()
OWNER_PASSWORD = os.getenv("OWNER_PASSWORD", "change-me").strip()

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USE_SSL"] = False
app.config["MAIL_USERNAME"] = MAIL_USERNAME
app.config["MAIL_PASSWORD"] = MAIL_PASSWORD
app.config["MAIL_DEFAULT_SENDER"] = MAIL_USERNAME
app.config["MAIL_TIMEOUT"] = 10

app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

mail = Mail(app)

MIX_OPTIONS = [
    "24-8-20BB", "24-8-40BB", "24-12-20BB", "27-12-20BB","30-18-20BB",
    "18-18-20N", "21-15-20N", "24-15-20N", "27-15-20N", "27-18-20N", "30-18-20N"
]

ORDER_PHONE = "0898-48-1805"

app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.jinja_env.auto_reload = True

init_db(app)
app.teardown_appcontext(close_db)

@app.context_processor
def inject_notification_status():
    try:
        db = get_db()
        row = db.execute(
            "SELECT COUNT(*) AS cnt FROM notifications WHERE is_read = FALSE"
        ).fetchone()
        has_unread = row["cnt"] > 0
    except Exception:
        has_unread = False

    return dict(has_unread=has_unread)

def extract_photo_url(message):
    if not message:
        return ""

    for line in message.splitlines():
        line = line.strip()
        if line.startswith("添付写真URL:"):
            return line.replace("添付写真URL:", "", 1).strip()

    return ""

def create_notification(notification_type, title="", message=""):
    db = get_db()
    db.execute(
        """
        INSERT INTO notifications (type, title, message)
        VALUES (%s, %s, %s)
        """,
        (notification_type, title, message)
    )
    db.commit() 

def log_mail_config(tag="MAIL"):
    print(f"=== {tag}: MAIL CONFIG CHECK ===")
    print("MAIL_SERVER =", app.config.get("MAIL_SERVER"))
    print("MAIL_PORT =", app.config.get("MAIL_PORT"))
    print("MAIL_USE_TLS =", app.config.get("MAIL_USE_TLS"))
    print("MAIL_USE_SSL =", app.config.get("MAIL_USE_SSL"))
    print("MAIL_USERNAME =", MAIL_USERNAME)
    print("MAIL_PASSWORD_SET =", bool(MAIL_PASSWORD))
    print("MAIL_TO =", MAIL_TO)
    print("MAIL_DEFAULT_SENDER =", app.config.get("MAIL_DEFAULT_SENDER"))
    print("=== END MAIL CONFIG CHECK ===")


def mail_settings_ready():
    return bool(MAIL_USERNAME and MAIL_PASSWORD and MAIL_TO)


def allowed_image(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in {"jpg", "jpeg", "png", "heic", "webp"}


def mask_phone(phone):
    phone = (phone or "").strip()
    if len(phone) >= 8:
        return f"{phone[:3]}****{phone[-4:]}"
    return "****"


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


def owner_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("owner_user"):
            flash("管理画面にログインしてください。", "error")
            return redirect(url_for("owner_login"))
        return view_func(*args, **kwargs)
    return wrapped


def get_news_list(limit=3):
    db = get_db()
    return db.execute(
        """
        SELECT id, title, body, notice_date
        FROM notices
        ORDER BY notice_date DESC, id DESC
        LIMIT %s
        """,
        (limit,)
    ).fetchall()


def get_news_all():
    db = get_db()
    return db.execute(
        """
        SELECT id, title, body, notice_date
        FROM notices
        ORDER BY notice_date DESC, id DESC
        """
    ).fetchall()


def get_news_item(news_id):
    db = get_db()
    return db.execute(
        """
        SELECT id, title, body, notice_date
        FROM notices
        WHERE id = %s
        """,
        (news_id,)
    ).fetchone()


def is_company_holiday(today):
    y = today.year

    new_year_holidays = {
        date(y, 1, 1), date(y, 1, 2), date(y, 1, 3),
        date(y, 1, 4), date(y, 12, 30), date(y, 12, 31),
    }
    obon_holidays = {
        date(y, 8, 13), date(y, 8, 14), date(y, 8, 15),
    }
    gw_holidays = {
        date(y, 5, 3), date(y, 5, 4), date(y, 5, 5),
    }

    return today in new_year_holidays or today in obon_holidays or today in gw_holidays


def get_business_status():
    now = datetime.now(timezone.utc) + timedelta(hours=9)
    today = now.date()
    current_time = now.time()

    start_time = time(7, 50)
    end_time = time(16, 30)

    if now.weekday() in [5, 6]:
        return "本日休業日"

    if is_company_holiday(today):
        return "本日休業日"

    if start_time <= current_time <= end_time:
        return "本日営業中　7:50〜16:30"

    return "営業時間外　7:50〜16:30"


@app.context_processor
def inject_common():
    now = datetime.now(timezone.utc) + timedelta(hours=9)
    return {
        "business_status": get_business_status(),
        "order_phone": ORDER_PHONE,
        "now_year": now.year,
        "news": get_news_list(3),
        "mask_phone": mask_phone
    }


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/sitemap.xml")
def sitemap():
    pages = []

    pages.append({
        "loc": "https://imanama.co.jp/",
        "lastmod": datetime.now().date().isoformat()
    })
    pages.append({
        "loc": "https://imanama.co.jp/contact",
        "lastmod": datetime.now().date().isoformat()
    })
    pages.append({
        "loc": "https://imanama.co.jp/news",
        "lastmod": datetime.now().date().isoformat()
    })
    pages.append({
        "loc": "https://imanama.co.jp/precheck",
        "lastmod": datetime.now().date().isoformat()
    })

    xml = render_template("sitemap.xml", pages=pages)
    response = make_response(xml)
    response.headers["Content-Type"] = "application/xml"
    return response


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        company = request.form.get("company", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()

        print("=== CONTACT POST START ===")
        print("company =", company)
        print("name =", name)
        print("email =", email)
        print("message_exists =", bool(message))

        if not company or not name or not email or not message:
            print("CONTACT VALIDATION ERROR: required fields missing")
            flash("会社名・お名前・メールアドレス・お問い合わせ内容を入力してください。", "error")
            return redirect(url_for("contact"))

        notify_title = f"お問い合わせ: {company} {name}"
        notify_message = f"""会社名: {company}
お名前: {name}
メール: {email}

内容:
{message}
"""

        try:
            print("=== CONTACT NOTIFICATION SAVE START ===")
            print(notify_message)

            create_notification(
                "contact",
                title=notify_title,
                message=notify_message
            )

            print("=== CONTACT NOTIFICATION SAVE SUCCESS ===")

        except Exception as e:
            print("=== CONTACT SAVE ERROR ===")
            print("error type =", type(e))
            print("error repr =", repr(e))
            traceback.print_exc()
            flash("お問い合わせの受付に失敗しました。", "error")
            return redirect(url_for("contact"))

        if mail_settings_ready():
            try:
                print("=== CONTACT MAIL SEND START ===")
                log_mail_config("CONTACT")

                msg = Message(
                    subject=notify_title,
                    recipients=[MAIL_TO],
                    body=notify_message
                )

                mail.send(msg)
                print("=== CONTACT MAIL SEND SUCCESS ===")

            except Exception as e:
                print("=== CONTACT MAIL SEND ERROR ===")
                print("error type =", type(e))
                print("error repr =", repr(e))
                traceback.print_exc()
        else:
            print("=== CONTACT MAIL SKIPPED: mail settings not ready ===")

        flash(f"お問い合わせを受け付けました。{name}様", "ok")
        return redirect(url_for("contact"))

    return render_template("contact.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        phone = request.form.get("phone", "").strip()

        db = get_db()

        user = db.execute(
            """
            SELECT id, company, name, phone
            FROM clients
            WHERE phone = %s AND is_active = true
            """,
            (phone,)
        ).fetchone()

        if user:
            session.permanent = True
            session["user"] = {
                "id": user["id"],
                "company": user["company"],
                "name": user["name"],
                "phone": user["phone"]
            }
            return redirect(url_for("dashboard"))

        flash("ログイン情報が正しくありません。", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/precheck")
def precheck():
    return render_template("precheck.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/map", methods=["GET", "POST"])
@login_required
def map_send():
    if request.method == "POST":
        lat = request.form.get("lat", "").strip()
        lng = request.form.get("lng", "").strip()
        map_url = request.form.get("map_url", "").strip()
        comment = request.form.get("comment", "").strip()
        location_method = request.form.get("location_method", "manual").strip()

        user = session.get("user", {})
        company = user.get("company", "")
        name = user.get("name", "")

        print("=== MAP POST START ===")
        print("lat =", lat)
        print("lng =", lng)
        print("map_url =", map_url)
        print("location_method =", location_method)
        print("comment_exists =", bool(comment))
        print("session_user =", user)

        if not lat or not lng:
            print("MAP VALIDATION ERROR: lat/lng missing")
            flash("緯度・経度を入力するか、現在地を取得してから送信してください。", "error")
            return redirect(url_for("map_send"))

        try:
            lat_num = float(lat)
            lng_num = float(lng)
        except ValueError:
            print("MAP VALIDATION ERROR: invalid lat/lng format")
            flash("緯度・経度の形式が正しくありません。", "error")
            return redirect(url_for("map_send"))

        if not (-90 <= lat_num <= 90) or not (-180 <= lng_num <= 180):
            print("MAP VALIDATION ERROR: lat/lng out of range")
            flash("緯度・経度の範囲が正しくありません。", "error")
            return redirect(url_for("map_send"))

        if not map_url:
            map_url = f"https://www.google.com/maps?q={lat},{lng}"

        method_label = "現在地取得" if location_method == "current" else "手動指定"

        notification_message = f"""会社名: {company}
担当者: {name}
指定方法: {method_label}
緯度: {lat}
経度: {lng}
Googleマップ: {map_url}

コメント:
{comment if comment else "なし"}"""

        try:
            print("=== MAP NOTIFICATION SAVE START ===")
            print(notification_message)

            create_notification(
                "map",
                title=f"現場地図送信: {company} {name}",
                message=notification_message
            )

            print("=== MAP NOTIFICATION SAVE SUCCESS ===")

            if mail_settings_ready():
                try:
                    log_mail_config("MAP_SEND")

                    msg = Message(
                        subject=f"現場地図送信: {company} {name}",
                        recipients=[MAIL_TO],
                        body=notification_message
                    )

                    mail.send(msg)
                    print("=== MAP MAIL SEND SUCCESS ===")

                except Exception as e:
                    print("=== MAP MAIL SEND ERROR ===")
                    print(repr(e))
                    traceback.print_exc()
            else:
                print("=== MAP MAIL SKIPPED: mail settings not ready ===")

            flash("現場地図を受け付けました。", "ok")
            return redirect(url_for("dashboard"))

        except Exception as e:
            print("=== MAP SAVE ERROR ===")
            print("error repr =", repr(e))
            traceback.print_exc()
            flash("現場地図の受付に失敗しました。", "error")
            return redirect(url_for("map_send"))

    return render_template("map.html")


@app.route("/mix-report", methods=["GET", "POST"])
@login_required
def mix_report():
    if request.method == "GET":
        return render_template(
            "mix_report.html",
            today=jst_today(),
            mix_options=MIX_OPTIONS
        )

    project = request.form.get("project", "").strip()
    report_date = request.form.get("report_date", "").strip() or jst_today()
    copies = request.form.get("copies", "2").strip() or "2"
    selected_mixes = request.form.getlist("mixes")
    custom_mix = request.form.get("custom_mix", "").strip()
    note = request.form.get("note", "").strip()
    photo = request.files.get("photo_camera")
    if not photo or photo.filename == "":
        photo = request.files.get("photo_library")

    print("=== MIX REPORT POST START ===")
    print("project =", project)
    print("report_date =", report_date)
    print("copies =", copies)
    print("selected_mixes =", selected_mixes)
    print("custom_mix =", custom_mix)
    print("note_exists =", bool(note))
    print("photo_exists =", bool(photo))
    print("photo_filename =", photo.filename if photo else None)

    if not photo or photo.filename == "":
        print("MIX REPORT VALIDATION ERROR: photo missing")
        flash("工事番号・工事名が写った写真を添付してください。", "error")
        return render_template("mix_report.html", today=report_date, mix_options=MIX_OPTIONS)

    if not allowed_image(photo.filename):
        print("MIX REPORT VALIDATION ERROR: invalid file type")
        flash("写真は JPG / JPEG / PNG / HEIC / WEBP を使用してください。", "error")
        return render_template("mix_report.html", today=report_date, mix_options=MIX_OPTIONS)

    all_mixes = [m.strip() for m in selected_mixes if m.strip()]
    if custom_mix:
        all_mixes.extend([x.strip() for x in custom_mix.replace("、", ",").split(",") if x.strip()])

    unique_mixes = []
    seen = set()
    for m in all_mixes:
        if m not in seen:
            unique_mixes.append(m)
            seen.add(m)

    print("unique_mixes =", unique_mixes)

    if not unique_mixes:
        print("MIX REPORT VALIDATION ERROR: no mixes selected")
        flash("配合を1つ以上選択、または直接入力してください。", "error")
        return render_template("mix_report.html", today=report_date, mix_options=MIX_OPTIONS)

    filename = secure_filename(photo.filename)
    timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
    save_name = f"{timestamp}_{filename}"
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], save_name)

    try:
        photo.save(save_path)
        print("photo saved to =", save_path)
    except Exception as e:
        print("PHOTO SAVE ERROR:", repr(e))
        traceback.print_exc()
        flash("写真の保存に失敗しました。", "error")
        return render_template("mix_report.html", today=report_date, mix_options=MIX_OPTIONS)

    user = session.get("user", {})
    company = user.get("company", "")
    name = user.get("name", "")

    photo_url = url_for("uploaded_file", filename=save_name, _external=True)

    notification_message = f"""会社名: {company}
担当者: {name}

工事名: {project or "未入力"}
配合報告書の日付: {report_date}
部数: {copies}部

配合:
{", ".join(unique_mixes)}

備考:
{note or "なし"}

添付写真URL: {photo_url}
"""

    try:
        print("=== MIX REPORT NOTIFICATION SAVE START ===")
        print(notification_message)

        create_notification(
            "mix_report",
            title=f"配合報告書依頼: {company} {name}",
            message=notification_message
        )

        if mail_settings_ready():
            try:
                log_mail_config("MIX_REPORT")

                msg = Message(
                    subject=f"配合報告書依頼: {company} {name}",
                    recipients=[MAIL_TO],
                    body=notification_message
                )

                with open(save_path, "rb") as f:
                    data = f.read()

                ext = filename.rsplit(".", 1)[-1].lower()
                mime_map = {
                    "jpg": "image/jpeg",
                    "jpeg": "image/jpeg",
                    "png": "image/png",
                    "webp": "image/webp",
                    "heic": "image/heic",
                }

                msg.attach(
                    filename=filename,
                    content_type=mime_map.get(ext, "application/octet-stream"),
                    data=data
                )

                mail.send(msg)
                print("=== MAIL SEND SUCCESS ===")

            except Exception as e:
                print("=== MAIL SEND ERROR ===")
                print(repr(e))
                traceback.print_exc()

        print("=== MIX REPORT NOTIFICATION SAVE SUCCESS ===")
        flash("配合報告書の依頼を受け付けました。", "ok")
        return redirect(url_for("dashboard"))

    except Exception as e:
        print("=== MIX REPORT NOTIFICATION SAVE ERROR ===")
        print("error repr =", repr(e))
        traceback.print_exc()
        flash("配合報告書依頼の受付に失敗しました。", "error")
        return render_template("mix_report.html", today=report_date, mix_options=MIX_OPTIONS)

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/price")
@login_required
def price():
    return render_template("price.html")

@app.route("/client/contact", methods=["GET", "POST"])
@login_required
def client_contact():
    user = session.get("user", {})

    if request.method == "POST":
        company = request.form.get("company", "").strip()
        name = request.form.get("name", "").strip()
        contact = request.form.get("contact", "").strip()
        message = request.form.get("message", "").strip()

        print("=== CLIENT CONTACT POST START ===")
        print("company =", company)
        print("name =", name)
        print("contact =", contact)
        print("message_exists =", bool(message))
        print("session_user =", user)

        # 空ならログイン情報で補完
        if not company:
            company = user.get("company", "")
        if not name:
            name = user.get("name", "")
        if not contact:
            contact = user.get("phone", "")

        if not message:
            print("CLIENT CONTACT VALIDATION ERROR: message missing")
            flash("内容を入力してください", "error")
            return redirect(url_for("client_contact"))

        # 件名を共通化
        notify_title = f"得意先お問い合わせ：{company} {name}".strip()

        # 管理画面表示用メッセージ
        notify_message = f"""会社名: {company or "未入力"}
担当者: {name or "未入力"}
連絡先: {contact or "未入力"}

内容:
{message}
"""

        # 1) まず通知として保存（これが本体）
        try:
            print("=== CLIENT CONTACT NOTIFICATION SAVE START ===")
            print(notify_message)

            db = get_db()
            with db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notifications (type, title, message, is_read)
                    VALUES (%s, %s, %s, FALSE)
                    """,
                    ("client_contact", notify_title, notify_message)
                )
            db.commit()

            print("=== CLIENT CONTACT NOTIFICATION SAVE SUCCESS ===")

        except Exception as e:
            db.rollback()
            print("=== CLIENT CONTACT NOTIFICATION SAVE ERROR ===")
            print(repr(e))
            traceback.print_exc()
            flash("お問い合わせの保存に失敗しました。", "error")
            return redirect(url_for("client_contact"))

        # 2) メール送信（失敗しても問い合わせ自体は保存済み）
        if mail_settings_ready():
            try:
                print("=== CLIENT CONTACT MAIL SEND START ===")
                log_mail_config("CLIENT_CONTACT")

                msg = Message(
                    subject=notify_title,
                    recipients=[MAIL_TO],
                    body=notify_message
                )

                mail.send(msg)
                print("=== CLIENT CONTACT MAIL SEND SUCCESS ===")

            except Exception as e:
                print("=== CLIENT CONTACT MAIL SEND ERROR ===")
                print(repr(e))
                traceback.print_exc()
        else:
            print("=== CLIENT CONTACT MAIL SKIPPED: mail settings not ready ===")

        flash("お問い合わせを受け付けました。", "ok")
        return redirect(url_for("client_contact"))

    return render_template(
        "contact_client.html",
        company=user.get("company", ""),
        name=user.get("name", ""),
        contact=user.get("phone", "")
    )

@app.route("/news")
def news_list():
    return render_template("news_list.html", news=get_news_all())


@app.route("/news/<int:news_id>")
def news_detail(news_id):
    item = get_news_item(news_id)
    if not item:
        abort(404)
    return render_template("news_detail.html", item=item)


@app.route("/owner/login", methods=["GET", "POST"])
def owner_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == OWNER_USERNAME and password == OWNER_PASSWORD:
            session.permanent = True
            session["owner_user"] = username
            flash("管理画面にログインしました。", "ok")
            return redirect(url_for("owner_dashboard"))

        flash("管理IDまたはパスワードが違います。", "error")
        return redirect(url_for("owner_login"))

    return render_template("owner_login.html")


@app.route("/owner/logout")
def owner_logout():
    session.pop("owner_user", None)
    flash("管理画面からログアウトしました。", "ok")
    return redirect(url_for("index"))


@app.route("/owner")
@owner_required
def owner_dashboard():
    db = get_db()
    client_count = db.execute("SELECT COUNT(*) AS cnt FROM clients").fetchone()["cnt"]
    notice_count = db.execute("SELECT COUNT(*) AS cnt FROM notices").fetchone()["cnt"]
    unread_notification_count = db.execute(
        "SELECT COUNT(*) AS cnt FROM notifications WHERE is_read = FALSE"
    ).fetchone()["cnt"]

    latest_notices = db.execute(
        """
        SELECT id, title, body, notice_date
        FROM notices
        ORDER BY notice_date DESC, id DESC
        LIMIT 5
        """
    ).fetchall()

    return render_template(
        "owner_dashboard.html",
        client_count=client_count,
        notice_count=notice_count,
        unread_notification_count=unread_notification_count,
        latest_notices=latest_notices
    )


@app.route("/owner/clients")
@owner_required
def owner_clients():
    db = get_db()
    clients = db.execute(
        """
        SELECT id, company, name, phone, is_active, created_at
        FROM clients
        ORDER BY id DESC
        """
    ).fetchall()
    return render_template("owner_clients.html", clients=clients)


@app.route("/owner/clients/new", methods=["GET", "POST"])
@owner_required
def owner_client_new():
    if request.method == "POST":
        company = request.form.get("company", "").strip()
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()

        form_client = {
            "company": company,
            "name": name,
            "phone": phone
        }

        if not company or not name or not phone:
            flash("会社名・担当者名・電話番号を入力してください。", "error")
            return render_template("owner_client_form.html", mode="new", client=form_client)

        db = get_db()
        try:
            db.execute(
                """
                INSERT INTO clients (company, name, phone, is_active)
                VALUES (%s, %s, %s, TRUE)
                """,
                (company, name, phone)
            )
            db.commit()
            flash("顧客を登録しました。", "ok")
            return redirect(url_for("owner_clients"))

        except Exception as e:
            print("owner_client_new error:", e)
            db.rollback()
            flash("登録に失敗しました。電話番号が重複している可能性があります。", "error")
            return render_template("owner_client_form.html", mode="new", client=form_client)

    return render_template("owner_client_form.html", mode="new", client={})


@app.route("/owner/clients/<int:client_id>/edit", methods=["GET", "POST"])
@owner_required
def owner_client_edit(client_id):
    db = get_db()
    client = db.execute(
        """
        SELECT id, company, name, phone, is_active, created_at
        FROM clients
        WHERE id = %s
        """,
        (client_id,)
    ).fetchone()

    if not client:
        abort(404)

    if request.method == "POST":
        company = request.form.get("company", "").strip()
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()

        form_client = {
            "id": client_id,
            "company": company,
            "name": name,
            "phone": phone,
            "is_active": client["is_active"]
        }

        if not company or not name or not phone:
            flash("会社名・担当者名・電話番号を入力してください。", "error")
            return render_template("owner_client_form.html", mode="edit", client=form_client)

        try:
            db.execute(
                """
                UPDATE clients
                SET company = %s, name = %s, phone = %s
                WHERE id = %s
                """,
                (company, name, phone, client_id)
            )
            db.commit()
            flash("顧客情報を更新しました。", "ok")
            return redirect(url_for("owner_clients"))

        except Exception as e:
            print("owner_client_edit error:", e)
            db.rollback()
            flash("更新に失敗しました。電話番号が重複している可能性があります。", "error")
            return render_template("owner_client_form.html", mode="edit", client=form_client)

    return render_template("owner_client_form.html", mode="edit", client=client)


@app.route("/owner/clients/<int:client_id>/toggle", methods=["POST"])
@owner_required
def owner_client_toggle(client_id):
    db = get_db()
    client = db.execute(
        "SELECT id, is_active FROM clients WHERE id = %s",
        (client_id,)
    ).fetchone()

    if not client:
        abort(404)

    new_status = not client["is_active"]
    db.execute("UPDATE clients SET is_active = %s WHERE id = %s", (new_status, client_id))
    db.commit()

    flash("利用状態を更新しました。", "ok")
    return redirect(url_for("owner_clients"))


@app.route("/owner/clients/<int:client_id>/delete", methods=["POST"])
@owner_required
def owner_client_delete(client_id):
    db = get_db()
    client = db.execute("SELECT id FROM clients WHERE id = %s", (client_id,)).fetchone()

    if not client:
        abort(404)

    db.execute("DELETE FROM clients WHERE id = %s", (client_id,))
    db.commit()

    flash("顧客を削除しました。", "ok")
    return redirect(url_for("owner_clients"))


@app.route("/owner/notices")
@owner_required
def owner_notices():
    notices = get_news_all()
    return render_template("owner_notices.html", notices=notices)


@app.route("/owner/notices/new", methods=["GET", "POST"])
@owner_required
def owner_notice_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        notice_date = request.form.get("notice_date", "").strip()

        notice_form = {
            "title": title,
            "body": body,
            "notice_date": notice_date
        }

        if not title or not body or not notice_date:
            flash("掲載日・タイトル・本文を入力してください。", "error")
            return render_template("owner_notice_form.html", mode="new", notice=notice_form)

        db = get_db()
        db.execute(
            "INSERT INTO notices (title, body, notice_date) VALUES (%s, %s, %s)",
            (title, body, notice_date)
        )
        db.commit()

        flash("お知らせを投稿しました。", "ok")
        return redirect(url_for("owner_notices"))

    return render_template(
        "owner_notice_form.html",
        mode="new",
        notice={"notice_date": date.today().isoformat()}
    )


@app.route("/owner/notices/<int:notice_id>/edit", methods=["GET", "POST"])
@owner_required
def owner_notice_edit(notice_id):
    db = get_db()
    notice = db.execute(
        "SELECT id, title, body, notice_date FROM notices WHERE id = %s",
        (notice_id,)
    ).fetchone()

    if not notice:
        abort(404)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        notice_date = request.form.get("notice_date", "").strip()

        notice_form = {
            "id": notice_id,
            "title": title,
            "body": body,
            "notice_date": notice_date
        }

        if not title or not body or not notice_date:
            flash("掲載日・タイトル・本文を入力してください。", "error")
            return render_template("owner_notice_form.html", mode="edit", notice=notice_form)

        db.execute(
            "UPDATE notices SET title = %s, body = %s, notice_date = %s WHERE id = %s",
            (title, body, notice_date, notice_id)
        )
        db.commit()

        flash("お知らせを更新しました。", "ok")
        return redirect(url_for("owner_notices"))

    return render_template("owner_notice_form.html", mode="edit", notice=notice)


@app.route("/owner/notices/<int:notice_id>/delete", methods=["POST"])
@owner_required
def owner_notice_delete(notice_id):
    db = get_db()
    notice = db.execute("SELECT id FROM notices WHERE id = %s", (notice_id,)).fetchone()

    if not notice:
        abort(404)

    db.execute("DELETE FROM notices WHERE id = %s", (notice_id,))
    db.commit()

    flash("お知らせを削除しました。", "ok")
    return redirect(url_for("owner_notices"))

@app.route("/owner/notifications")
@owner_required
def owner_notifications():
    db = get_db()
    rows = db.execute(
        """
        SELECT id, type, title, message, is_read, created_at
        FROM notifications
        ORDER BY is_read ASC, created_at DESC, id DESC
        """
    ).fetchall()

    notifications = []
    for row in rows:
        item = dict(row)
        item["photo_url"] = extract_photo_url(item.get("message", ""))
        notifications.append(item)

    return render_template("owner_notifications.html", notifications=notifications)

@app.route("/owner/notifications/<int:notification_id>/read", methods=["POST"])
@owner_required
def owner_notification_read(notification_id):
    db = get_db()
    notification = db.execute(
        "SELECT id FROM notifications WHERE id = %s",
        (notification_id,)
    ).fetchone()

    if not notification:
        abort(404)

    db.execute(
        "UPDATE notifications SET is_read = TRUE WHERE id = %s",
        (notification_id,)
    )
    db.commit()

    flash("通知を確認済みにしました。", "ok")
    return redirect(url_for("owner_notifications"))

@app.route("/owner/notifications/<int:notification_id>/unread", methods=["POST"])
@owner_required
def owner_notification_unread(notification_id):
    db = get_db()
    notification = db.execute(
        "SELECT id FROM notifications WHERE id = %s",
        (notification_id,)
    ).fetchone()

    if not notification:
        abort(404)

    db.execute(
        "UPDATE notifications SET is_read = FALSE WHERE id = %s",
        (notification_id,)
    )
    db.commit()

    flash("通知を未確認に戻しました。", "ok")
    return redirect(url_for("owner_notifications"))    

@app.route("/owner/notifications/<int:notification_id>/delete", methods=["POST"])
@owner_required
def owner_notification_delete(notification_id):
    db = get_db()
    notification = db.execute(
        "SELECT id FROM notifications WHERE id = %s",
        (notification_id,)
    ).fetchone()

    if not notification:
        abort(404)

    db.execute(
        "DELETE FROM notifications WHERE id = %s",
        (notification_id,)
    )
    db.commit()

    flash("通知を削除しました。", "ok")
    return redirect(url_for("owner_notifications"))        

@app.route("/init-db")
def init_db_column():
    db = get_db()
    db.execute("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS ocr_text TEXT;")
    db.commit()
    return "OK"

if __name__ == "__main__":
    app.run(debug=True)