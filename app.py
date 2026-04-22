from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = "library_secret_key"
DB_NAME = "library.db"

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # BOOKS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        author TEXT,
        isbn TEXT UNIQUE,
        publisher TEXT,
        year INTEGER,
        edition TEXT,
        category TEXT,
        total_copies INTEGER,
        available_copies INTEGER,
        shelf_code TEXT
    )
    """)

    # USERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    # BORROW RECORDS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS borrow_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        book_id INTEGER,
        borrow_date TEXT,
        due_date TEXT,
        return_date TEXT,
        fine INTEGER DEFAULT 0
    )
    """)

    # default admin
    cursor.execute("SELECT * FROM users WHERE username='admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                       ("admin", "1234", "admin"))

    conn.commit()
    conn.close()


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p))
        user = cur.fetchone()
        conn.close()

        if user:
            session["user"] = u
            session["role"] = user[3]
            return redirect("/")

        return "Invalid login"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------- HOME + SEARCH ----------------
@app.route("/")
def home():
    if "user" not in session:
        return redirect("/login")

    search = request.args.get("search")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    if search:
        cur.execute("""
            SELECT * FROM books
            WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ? OR category LIKE ?
        """, (f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"))
    else:
        cur.execute("SELECT * FROM books")

    books = cur.fetchall()
    conn.close()

    return render_template("index.html", books=books, role=session["role"])


# ---------------- ADD BOOK ----------------
@app.route("/add", methods=["POST"])
def add():
    if session.get("role") != "admin":
        return "Access denied"

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO books (
            title, author, isbn, publisher, year,
            edition, category, total_copies, available_copies, shelf_code
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        request.form["title"],
        request.form["author"],
        request.form["isbn"],
        request.form["publisher"],
        request.form["year"],
        request.form["edition"],
        request.form["category"],
        request.form["copies"],
        request.form["copies"],
        request.form["shelf"]
    ))

    conn.commit()
    conn.close()
    return redirect("/")


# ---------------- BORROW BOOK ----------------
@app.route("/borrow/<int:book_id>")
def borrow(book_id):
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT available_copies FROM books WHERE id=?", (book_id,))
    book = cur.fetchone()

    if book and book[0] > 0:
        borrow_date = datetime.now()
        due_date = borrow_date + timedelta(days=7)

        cur.execute("""
            INSERT INTO borrow_records (user, book_id, borrow_date, due_date)
            VALUES (?, ?, ?, ?)
        """, (session["user"], book_id, borrow_date, due_date))

        cur.execute("""
            UPDATE books
            SET available_copies = available_copies - 1
            WHERE id=?
        """, (book_id,))

    conn.commit()
    conn.close()

    return redirect("/")


# ---------------- RETURN BOOK ----------------
@app.route("/return/<int:record_id>")
def return_book(record_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT book_id, due_date FROM borrow_records WHERE id=?", (record_id,))
    data = cur.fetchone()

    if data:
        book_id, due_date = data
        return_date = datetime.now()

        fine = 0
        if return_date > datetime.fromisoformat(due_date):
            fine = 50  # simple fine rule

        cur.execute("""
            UPDATE borrow_records
            SET return_date=?, fine=?
            WHERE id=?
        """, (return_date, fine, record_id))

        cur.execute("""
            UPDATE books
            SET available_copies = available_copies + 1
            WHERE id=?
        """, (book_id,))

    conn.commit()
    conn.close()

    return redirect("/")
# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    return render_template("dashboard.html")
# ---------------- STATS API ----------------
@app.route("/stats")
def stats():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM books")
    total_books = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM borrow_records WHERE return_date IS NULL")
    borrowed = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(available_copies), 0) FROM books")
    available = cur.fetchone()[0]

    conn.close()

    return {
        "total_books": total_books,
        "borrowed": borrowed,
        "available": available
    }


# ---------------- RUN ----------------
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)