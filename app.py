from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
import pandas as pd

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SECRET_KEY'] = 'secret'

db = SQLAlchemy(app)

# ================= MODELS =================

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    author = db.Column(db.String(200))
    subject = db.Column(db.String(100))
    available = db.Column(db.Integer)

# ================= INIT =================

@app.before_first_request
def setup():
    db.create_all()

# ================= ROUTES =================

@app.route('/')
def index():
    books = Book.query.all()
    return render_template("index.html", books=books)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == "admin" and request.form['password'] == "1234":
            return redirect('/')
    return render_template("login.html")

@app.route('/add', methods=['POST'])
def add_book():
    book = Book(
        title=request.form['title'],
        author=request.form['author'],
        subject=request.form['subject'],
        available=int(request.form['available'])
    )
    db.session.add(book)
    db.session.commit()
    return redirect('/')

@app.route('/borrow/<int:id>')
def borrow(id):
    book = Book.query.get(id)
    if book.available > 0:
        book.available -= 1
        db.session.commit()
    return redirect('/')

@app.route('/return/<int:id>')
def return_book(id):
    book = Book.query.get(id)
    book.available += 1
    db.session.commit()
    return redirect('/')

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    df = pd.read_csv(file)

    for _, row in df.iterrows():
        book = Book(
            title=row['title'],
            author=row['author'],
            subject=row['subject'],
            available=row['available']
        )
        db.session.add(book)

    db.session.commit()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
