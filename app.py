from functools import wraps
import json
import os
import sqlite3
from urllib.parse import quote
from urllib.request import Request, urlopen

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    send_from_directory,
    request,
    session,
    url_for,
)
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-this-secret")
app.config["DATABASE"] = os.path.join(os.path.abspath(os.path.dirname(__file__)), "videotheek.db")
CORS(app)


def get_db_connection():
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_database():
    connection = get_db_connection()
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS film (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'available'
                CHECK (status IN ('available', 'rented', 'reserved')),
            rented_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            reserved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            description TEXT,
            image_url TEXT
        );
        CREATE TABLE IF NOT EXISTS logging (
            id INTEGER PRIMARY KEY,
            film_id INTEGER NOT NULL REFERENCES film(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            action TEXT NOT NULL CHECK (action IN ('rented', 'returned', 'reserved', 'cancelled')),
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    if connection.execute("SELECT COUNT(*) FROM film").fetchone()[0] == 0:
        connection.executemany(
            "INSERT INTO film (title, status) VALUES (?, 'available')",
            [
                ("The Matrix",),
                ("Back to the Future",),
                ("Jurassic Park",),
                ("The Lion King",),
                ("Inception",),
            ],
        )
    connection.commit()
    connection.close()


def current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    connection = get_db_connection()
    user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    connection.close()
    return user


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authenticatie vereist"}), 401
            flash("Log eerst in om deze pagina te bekijken.", "warning")
            return redirect(url_for("login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user()["role"] != "admin":
            if request.path.startswith("/api/"):
                return jsonify({"error": "Administratorrechten vereist"}), 403
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def log_action(connection, film_id, action, user_id):
    connection.execute(
        "INSERT INTO logging (film_id, user_id, action) VALUES (?, ?, ?)",
        (film_id, user_id, action),
    )


def film_from_row(row):
    return dict(row)


def enrich_film(film):
    if film["description"] and film["image_url"]:
        return film
    try:
        request_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(
            film["title"].replace(" ", "_")
        )
        http_request = Request(request_url, headers={"User-Agent": "AlfaFlix/1.0"})
        with urlopen(http_request, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
        description = data.get("extract")
        image_url = data.get("thumbnail", {}).get("source")
        connection = get_db_connection()
        connection.execute(
            "UPDATE film SET description = ?, image_url = ? WHERE id = ?",
            (description, image_url, film["id"]),
        )
        connection.commit()
        connection.close()
        film["description"] = description
        film["image_url"] = image_url
    except (OSError, ValueError, KeyError):
        film["description"] = film["description"] or "Geen externe filminformatie beschikbaar."
    return film


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/videotheek")
@login_required
def videotheek():
    connection = get_db_connection()
    films = [film_from_row(row) for row in connection.execute("SELECT * FROM film ORDER BY title")]
    connection.close()
    films = [enrich_film(film) for film in films]
    return render_template("videotheek.html", films=films)


@app.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 8:
            flash("Gebruikersnaam is minimaal 3 tekens en wachtwoord minimaal 8 tekens.", "danger")
            return render_template("register.html")
        connection = get_db_connection()
        try:
            role = "admin" if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0 else "user"
            connection.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), role),
            )
            connection.commit()
        except sqlite3.IntegrityError:
            flash("Deze gebruikersnaam bestaat al.", "danger")
            connection.close()
            return render_template("register.html")
        connection.close()
        flash("Account aangemaakt. Je kunt nu inloggen.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        connection = get_db_connection()
        user = connection.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        connection.close()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(request.form.get("next") or url_for("videotheek"))
        flash("Ongeldige gebruikersnaam of wachtwoord.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Je bent uitgelogd.", "success")
    return redirect(url_for("home"))


@app.post("/films/<int:film_id>/rent")
@login_required
def rent_film(film_id):
    connection = get_db_connection()
    film = connection.execute("SELECT * FROM film WHERE id = ?", (film_id,)).fetchone()
    if film is None:
        connection.close()
        abort(404)
    if film["status"] != "available":
        flash("Deze dvd is niet beschikbaar.", "warning")
    else:
        connection.execute(
            "UPDATE film SET status = 'rented', rented_by = ? WHERE id = ?",
            (session["user_id"], film_id),
        )
        log_action(connection, film_id, "rented", session["user_id"])
        connection.commit()
        flash("Dvd geleend.", "success")
    connection.close()
    return redirect(url_for("videotheek"))


@app.post("/films/<int:film_id>/return")
@login_required
def return_film(film_id):
    connection = get_db_connection()
    film = connection.execute("SELECT * FROM film WHERE id = ?", (film_id,)).fetchone()
    if film is None:
        connection.close()
        abort(404)
    if film["status"] != "rented" or (
        film["rented_by"] not in (None, session["user_id"])
        and current_user()["role"] != "admin"
    ):
        flash("Deze dvd kan niet door jou worden teruggebracht.", "warning")
    else:
        connection.execute(
            "UPDATE film SET status = 'available', rented_by = NULL WHERE id = ?", (film_id,)
        )
        log_action(connection, film_id, "returned", session["user_id"])
        connection.commit()
        flash("Dvd teruggebracht.", "success")
    connection.close()
    return redirect(url_for("videotheek"))


@app.post("/films/<int:film_id>/reserve")
@login_required
def reserve_film(film_id):
    connection = get_db_connection()
    film = connection.execute("SELECT * FROM film WHERE id = ?", (film_id,)).fetchone()
    if film is None:
        connection.close()
        abort(404)
    if film["status"] != "available":
        flash("Deze dvd is niet beschikbaar voor reservering.", "warning")
    else:
        connection.execute(
            "UPDATE film SET status = 'reserved', reserved_by = ? WHERE id = ?",
            (session["user_id"], film_id),
        )
        log_action(connection, film_id, "reserved", session["user_id"])
        connection.commit()
        flash("Dvd gereserveerd.", "success")
    connection.close()
    return redirect(url_for("videotheek"))


@app.route("/admin")
@admin_required
def admin():
    connection = get_db_connection()
    films = connection.execute("SELECT * FROM film ORDER BY title").fetchall()
    logs = connection.execute(
        """
        SELECT logging.*, film.title, users.username
        FROM logging JOIN film ON film.id = logging.film_id
        LEFT JOIN users ON users.id = logging.user_id
        ORDER BY logging.timestamp DESC LIMIT 50
        """
    ).fetchall()
    connection.close()
    return render_template("admin.html", films=films, logs=logs)


@app.post("/admin/films")
@admin_required
def create_film():
    title = request.form.get("title", "").strip()
    if not title:
        flash("Een titel is verplicht.", "danger")
    else:
        connection = get_db_connection()
        connection.execute("INSERT INTO film (title, status) VALUES (?, 'available')", (title,))
        connection.commit()
        connection.close()
        flash("Dvd toegevoegd.", "success")
    return redirect(url_for("admin"))


@app.post("/admin/films/<int:film_id>/delete")
@admin_required
def delete_film(film_id):
    connection = get_db_connection()
    connection.execute("DELETE FROM film WHERE id = ?", (film_id,))
    connection.commit()
    connection.close()
    flash("Dvd verwijderd.", "success")
    return redirect(url_for("admin"))


@app.get("/api/films")
def api_list_films():
    connection = get_db_connection()
    films = [film_from_row(row) for row in connection.execute("SELECT * FROM film ORDER BY title")]
    connection.close()
    return jsonify(films)


@app.get("/api/films/<int:film_id>")
def api_get_film(film_id):
    connection = get_db_connection()
    film = connection.execute("SELECT * FROM film WHERE id = ?", (film_id,)).fetchone()
    connection.close()
    if film is None:
        return jsonify({"error": "Film niet gevonden"}), 404
    return jsonify(film_from_row(film))


@app.post("/api/films")
@admin_required
def api_create_film():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    if not title:
        return jsonify({"error": "title is verplicht"}), 400
    connection = get_db_connection()
    cursor = connection.execute("INSERT INTO film (title, status) VALUES (?, 'available')", (title,))
    connection.commit()
    film = connection.execute("SELECT * FROM film WHERE id = ?", (cursor.lastrowid,)).fetchone()
    connection.close()
    return jsonify(film_from_row(film)), 201


@app.put("/api/films/<int:film_id>")
@admin_required
def api_update_film(film_id):
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    status = data.get("status")
    if not title or status not in {"available", "rented", "reserved"}:
        return jsonify({"error": "title en geldige status zijn verplicht"}), 400
    connection = get_db_connection()
    cursor = connection.execute(
        "UPDATE film SET title = ?, status = ? WHERE id = ?", (title, status, film_id)
    )
    connection.commit()
    film = connection.execute("SELECT * FROM film WHERE id = ?", (film_id,)).fetchone()
    connection.close()
    if cursor.rowcount == 0:
        return jsonify({"error": "Film niet gevonden"}), 404
    return jsonify(film_from_row(film))


@app.delete("/api/films/<int:film_id>")
@admin_required
def api_delete_film(film_id):
    connection = get_db_connection()
    cursor = connection.execute("DELETE FROM film WHERE id = ?", (film_id,))
    connection.commit()
    connection.close()
    if cursor.rowcount == 0:
        return jsonify({"error": "Film niet gevonden"}), 404
    return "", 204


@app.post("/api/films/<int:film_id>/rent")
@login_required
def api_rent_film(film_id):
    connection = get_db_connection()
    film = connection.execute("SELECT * FROM film WHERE id = ?", (film_id,)).fetchone()
    if film is None:
        connection.close()
        return jsonify({"error": "Film niet gevonden"}), 404
    if film["status"] != "available":
        connection.close()
        return jsonify({"error": "Film is niet beschikbaar"}), 409
    connection.execute(
        "UPDATE film SET status = 'rented', rented_by = ? WHERE id = ?",
        (session["user_id"], film_id),
    )
    log_action(connection, film_id, "rented", session["user_id"])
    connection.commit()
    connection.close()
    return jsonify({"message": "Film geleend"})


@app.post("/api/films/<int:film_id>/reserve")
@login_required
def api_reserve_film(film_id):
    connection = get_db_connection()
    film = connection.execute("SELECT * FROM film WHERE id = ?", (film_id,)).fetchone()
    if film is None:
        connection.close()
        return jsonify({"error": "Film niet gevonden"}), 404
    if film["status"] != "available":
        connection.close()
        return jsonify({"error": "Film is niet beschikbaar"}), 409
    connection.execute(
        "UPDATE film SET status = 'reserved', reserved_by = ? WHERE id = ?",
        (session["user_id"], film_id),
    )
    log_action(connection, film_id, "reserved", session["user_id"])
    connection.commit()
    connection.close()
    return jsonify({"message": "Film gereserveerd"})


@app.post("/api/films/<int:film_id>/return")
@login_required
def api_return_film(film_id):
    connection = get_db_connection()
    film = connection.execute("SELECT * FROM film WHERE id = ?", (film_id,)).fetchone()
    if film is None:
        connection.close()
        return jsonify({"error": "Film niet gevonden"}), 404
    if film["status"] != "rented" or (
        film["rented_by"] not in (None, session["user_id"])
        and current_user()["role"] != "admin"
    ):
        connection.close()
        return jsonify({"error": "Deze film kan niet worden teruggebracht"}), 409
    connection.execute(
        "UPDATE film SET status = 'available', rented_by = NULL WHERE id = ?", (film_id,)
    )
    log_action(connection, film_id, "returned", session["user_id"])
    connection.commit()
    connection.close()
    return jsonify({"message": "Film teruggebracht"})


@app.get("/api/logging")
@admin_required
def api_logging():
    connection = get_db_connection()
    logs = connection.execute(
        """
        SELECT logging.id, film.title, users.username, logging.action, logging.timestamp
        FROM logging JOIN film ON film.id = logging.film_id
        LEFT JOIN users ON users.id = logging.user_id
        ORDER BY logging.timestamp DESC
        """
    ).fetchall()
    connection.close()
    return jsonify([dict(log) for log in logs])


@app.get("/api/docs")
def api_docs():
    return redirect(url_for("swagger_ui"))


@app.get("/swagger.yaml")
def swagger_yaml():
    return send_from_directory(os.path.dirname(__file__), "swagger.yaml")


@app.get("/api/docs/ui")
def swagger_ui():
    return render_template("swagger.html")


@app.route("/opdracht")
def opdracht():
    return render_template("opdracht.html")


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="Je hebt geen toegang tot deze pagina."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="Pagina niet gevonden."), 404


create_database()

if __name__ == "__main__":
    app.run(debug=True)
