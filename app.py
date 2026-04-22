from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = "library_secret_key"
DB_NAME = "library.db"

# ---------------- INIT DB ----------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        author TEXT,
        isbn TEXT,
        category TEXT,
        total_copies INTEGER,
        available_copies INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS borrow_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        book_id INTEGER,
        borrow_date TEXT,
        due_date TEXT,
        return_date TEXT
    )
    """)

    # default users
    cur.execute("SELECT * FROM users WHERE username='admin'")
    if not cur.fetchone():
        cur.execute("INSERT INTO users (username,password,role) VALUES (?,?,?)",
                    ("admin","1234","admin"))

    cur.execute("SELECT * FROM users WHERE username='user'")
    if not cur.fetchone():
        cur.execute("INSERT INTO users (username,password,role) VALUES (?,?,?)",
                    ("user","1111","user"))

    conn.commit()
    conn.close()

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (u,p))
        user = cur.fetchone()
        conn.close()

        if user:
            session["user"] = user[1]
            session["role"] = user[3]
            return redirect("/")

        return "Invalid login"

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- HOME ----------------
@app.route("/")
def home():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM books")
    books = cur.fetchall()
    conn.close()

    return render_template("index.html", books=books, role=session["role"])

# ---------------- ADD BOOK (ADMIN ONLY) ----------------
@app.route("/add", methods=["POST"])
def add():
    if session.get("role") != "admin":
        return "Access denied"

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    copies = int(request.form["copies"])

    cur.execute("""
    INSERT INTO books (title,author,isbn,category,total_copies,available_copies)
    VALUES (?,?,?,?,?,?)
    """, (
        request.form["title"],
        request.form["author"],
        request.form["isbn"],
        request.form["category"],
        copies,
        copies
    ))

    conn.commit()
    conn.close()
    return redirect("/")

# ---------------- BORROW ----------------
@app.route("/borrow/<int:book_id>")
def borrow(book_id):
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT available_copies FROM books WHERE id=?", (book_id,))
    book = cur.fetchone()

    if book and book[0] > 0:
        now = datetime.now()
        due = now + timedelta(days=7)

        cur.execute("""
        INSERT INTO borrow_records (user, book_id, borrow_date, due_date)
        VALUES (?,?,?,?)
        """, (session["user"], book_id, now, due))

        cur.execute("""
        UPDATE books SET available_copies = available_copies - 1
        WHERE id=?
        """, (book_id,))

    conn.commit()
    conn.close()
    return redirect("/")

# ---------------- RETURN ----------------
@app.route("/return/<int:record_id>")
def return_book(record_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT book_id FROM borrow_records WHERE id=?", (record_id,))
    data = cur.fetchone()

    if data:
        book_id = data[0]

        cur.execute("""
        UPDATE borrow_records SET return_date=? WHERE id=?
        """, (datetime.now(), record_id))

        cur.execute("""
        UPDATE books SET available_copies = available_copies + 1
        WHERE id=?
        """, (book_id,))

    conn.commit()
    conn.close()
    return redirect("/history")

# ---------------- HISTORY ----------------
@app.route("/history")
def history():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    SELECT borrow_records.id, user, title, borrow_date, due_date, return_date
    FROM borrow_records
    JOIN books ON books.id = borrow_records.book_id
    """)
    records = cur.fetchall()

    conn.close()
    return render_template("history.html", records=records)

# ---------------- DASHBOARD STATS ----------------
@app.route("/stats")
def stats():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM books")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM borrow_records WHERE return_date IS NULL")
    borrowed = cur.fetchone()[0]

    cur.execute("SELECT SUM(available_copies) FROM books")
    available = cur.fetchone()[0] or 0

    conn.close()

    return jsonify({
        "total_books": total,
        "borrowed": borrowed,
        "available": available
    })

# ---------------- RUN ----------------
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)