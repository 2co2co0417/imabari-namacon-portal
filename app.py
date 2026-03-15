from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from functools import wraps
from datetime import datetime, date, time
from db import get_db, close_db, init_db
from flask_mail import Mail, Message
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import os
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

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
    "24-8-20BB", "24-8-40BB", "24-12-20BB", "30-18-20BB",
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
    now = datetime.now()
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
    now = datetime.now()
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


@app.route("/mail-test")
def mail_test():
    try:
        print("=== MAIL TEST START ===")
        log_mail_config("MAIL TEST")

        if not mail_settings_ready():
            return "メール設定不足"

        msg = Message(
            subject="送信テスト",
            recipients=[MAIL_TO],
            body="これは今治生コンポータルの送信テストです。",
            sender=MAIL_USERNAME
        )

        print("MAIL TEST MESSAGE BUILD OK")
        mail.send(msg)
        print("MAIL TEST SEND SUCCESS")
        return "メール送信成功"

    except Exception as e:
        print("=== MAIL TEST ERROR ===")
        print("error repr =", repr(e))
        traceback.print_exc()
        return f"メール送信失敗: {repr(e)}"


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

        try:
            create_notification(
                "contact",
                title=f"お問い合わせ: {company} {name}",
                message=f"メール: {email}\n\n{message}"
            )

            print("=== CONTACT SAVE SUCCESS ===")
            flash(f"お問い合わせを受け付けました。{name}様", "ok")
            return redirect(url_for("contact"))

        except BaseException as e:
            print("=== CONTACT SAVE ERROR ===")
            print("error type =", type(e))
            print("error repr =", repr(e))
            traceback.print_exc()
            flash("お問い合わせの受付に失敗しました。", "error")
            return redirect(url_for("contact"))

    return render_template("contact.html")


@app.route("/login", methods=["GET", "POST"])
def login():
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
    session.pop("user", None)
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
            flash("緯度・経度の形式が正しくありません。", "error")
            return redirect(url_for("map_send"))

        if not (-90 <= lat_num <= 90) or not (-180 <= lng_num <= 180):
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
            create_notification(
                "map",
                title=f"現場地図送信: {company} {name}",
                message=notification_message
            )

            print("=== MAP SAVE SUCCESS ===")
            flash("現場地図を受け付けました。", "ok")

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
            today=date.today().isoformat(),
            mix_options=MIX_OPTIONS
        )

    project = request.form.get("project", "").strip()
    report_date = request.form.get("report_date", "").strip() or date.today().isoformat()
    copies = request.form.get("copies", "2").strip() or "2"
    selected_mixes = request.form.getlist("mixes")
    custom_mix = request.form.get("custom_mix", "").strip()
    note = request.form.get("note", "").strip()
    photo = request.files.get("photo")

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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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

    subject = f"配合報告書依頼｜{project or '工事名未入力'}"
    body = f"""配合報告書の依頼がありました。

【依頼者】
会社名：{company}
氏名：{name}

【工事名】
{project or '未入力'}

【配合報告書の日付】
{report_date}

【部数】
{copies}部

【配合】
{", ".join(unique_mixes)}

【備考】
{note or 'なし'}
"""

    try:
        if not mail_settings_ready():
            log_mail_config("MIX REPORT")
            flash("メール設定が未完了です。管理者にご確認ください。", "error")
            return render_template("mix_report.html", today=report_date, mix_options=MIX_OPTIONS)

        log_mail_config("MIX REPORT BEFORE SEND")

        msg = Message(
            subject=subject,
            recipients=[MAIL_TO],
            body=body,
            sender=MAIL_USERNAME
        )

        with app.open_resource(save_path) as fp:
            file_data = fp.read()
            print("attachment_bytes =", len(file_data))
            msg.attach(
                filename=save_name,
                content_type=photo.content_type or "application/octet-stream",
                data=file_data
            )

        print("=== MIX REPORT MAIL BUILD OK ===")
        print("subject =", subject)
        print("recipients =", [MAIL_TO])
        print("sender =", MAIL_USERNAME)

        mail.send(msg)

        print("=== MIX REPORT MAIL SEND SUCCESS ===")
        flash("配合報告書の依頼を送信しました。", "success")
        return redirect(url_for("dashboard"))

    except Exception as e:
        print("=== MIX REPORT MAIL SEND ERROR ===")
        print("error repr =", repr(e))
        traceback.print_exc()
        flash("送信に失敗しました。メール設定をご確認ください。", "error")
        return render_template("mix_report.html", today=report_date, mix_options=MIX_OPTIONS)


@app.route("/price")
@login_required
def price():
    return render_template("price.html")


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
    notifications = db.execute(
        """
        SELECT id, type, title, message, is_read, created_at
        FROM notifications
        ORDER BY is_read ASC, created_at DESC, id DESC
        """
    ).fetchall()

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

if __name__ == "__main__":
    app.run(debug=True)