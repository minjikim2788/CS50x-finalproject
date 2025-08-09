from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash

# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///budget.db")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    # Forget any user_id
    session.clear()
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("error.html", msg = "must provide username")
        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("error.html", msg = "must provide password")
        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))
        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"],
                                                     request.form.get("password")):
            return render_template("error.html", msg = "invalid username and/or password")
        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        # Redirect user to home page
        return redirect("/")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out"""
    # Forget any user_id
    session.clear()
    # Redirect user to login form
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()
    # if user submits the form, check for possible errors and insert new user into users table
    if request.method == "POST":
        if not request.form.get("username"):
            return render_template("error.html", msg = "Username is required")
        if not request.form.get("password"):
            return render_template("error.html", msg = "Password is required")
        if not request.form.get("confirmation"):
            return render_template("error.html", msg = "Password confirmation is required")
        if request.form.get("password") != request.form.get("confirmation"):
            return render_template("error.html", msg = "Passwords do not match")
        try:
            db.execute("INSERT INTO users(username, hash, firstname, lastname) VALUES(?, ?, ?, ?)",
                       request.form.get("username"), generate_password_hash(request.form.get("password")), request.form.get("firstname"), request.form.get("lastname"))
            return redirect("/")
        except ValueError:
            return render_template("error.html", msg = "Username already exists")
    # user tries to access the register route using get request method, then display a register form to the user.
    else:
        return render_template("register.html")


@app.route("/")
@login_required
def home():
    user_id = session["user_id"]
    names = db.execute("SELECT firstname, lastname FROM users WHERE id = ?", user_id)
    total_income = db.execute("SELECT SUM(money) AS amount FROM finance WHERE user_id = ? AND type = ?", user_id, "deposit")
    total_expense = db.execute("SELECT SUM(money) AS amount FROM finance WHERE user_id = ? AND type = ?", user_id, "withdraw")
    values = db.execute("SELECT goal, balance FROM users WHERE id = ?", user_id)
    for value in values:
        amountleft = value["goal"] - value["balance"]
        progress_value = value["balance"] * 100 / value["goal"]
    recenthistories = db.execute("SELECT * FROM finance WHERE user_id = ? ORDER BY date DESC LIMIT 4", user_id)
    return render_template('index.html', names = names, total_income = total_income, total_expense = total_expense, values = values, amountleft = amountleft, progress_value = progress_value, recenthistories = recenthistories)

@app.route("/goal", methods=["GET", "POST"])
@login_required
def goal():
    """Let users set and edit financial goal"""
    user_id = session["user_id"]
    if request.method == "POST":
        amount = request.form.get("amount")
        if not amount:
            return render_template("error.html", msg = "Must provide amount")
        if float(amount) < 0:
            return render_template("error.html", msg = "Amount must be a positive number")
        db.execute("UPDATE users SET goal = ? WHERE id = ?", amount, user_id)
        return redirect("/goal")
    else:
        values = db.execute("SELECT goal, balance FROM users WHERE id = ?", user_id)
        for value in values:
            amountleft = value["goal"] - value["balance"]
            progress_value = value["balance"] * 100 / value["goal"]
        return render_template("goal.html", values = values, amountleft = amountleft, progress_value = progress_value)

@app.route("/income", methods=["GET", "POST"])
@login_required
def income():
    """Track their earning"""
    user_id = session["user_id"]
    if request.method == "POST":
        amount = float(request.form.get("amount"))
        if not amount:
            return render_template("error.html", msg = "Must provide amount")
        if float(amount) < 0:
            return render_template("error.html", msg = "Amount must be a positive number")
        date = request.form.get("date")
        if not date:
            return render_template("error.html", msg = "Must provide date")
        description = request.form.get("description")
        if not description:
            return render_template("error.html", msg = "Must provide description")
        transaction_type = "deposit"
        db.execute("UPDATE users SET balance = balance + ? WHERE id = ?", amount, user_id)
        db.execute("INSERT INTO finance (user_id, money, description, date, type) VALUES(?, ?, ?, ?, ?)",
                   user_id, amount, description, date, transaction_type)
        return redirect("/income")
    else:
        indatas = db.execute("SELECT * FROM finance WHERE user_id = ? AND type = ? ORDER BY date DESC", user_id, "deposit")
        total = db.execute("SELECT SUM(money) as sum FROM finance WHERE user_id = ? AND type = ? ORDER BY date DESC", user_id, "deposit")
        return render_template("income.html", indatas = indatas, total = total)

@app.route("/expense", methods=["GET", "POST"])
@login_required
def expense():
    """Track their spending"""
    user_id = session["user_id"]
    if request.method == "POST":
        amount = request.form.get("amount")
        if not amount or not amount.isdigit():
            return render_template("error.html", msg = "Must provide valid input for amount")
        if float(amount) < 0:
            return render_template("error.html", msg = "Amount must be a positive number")
        date = request.form.get("date")
        if not date:
            return render_template("error.html", msg = "Must porvide date")
        description = request.form.get("description")
        if not description:
            return render_template("error.html", msg = "Must provide description")
        transaction_type = "withdraw"
        db.execute("UPDATE users SET balance = balance - ? WHERE id = ?", amount, user_id)
        db.execute("INSERT INTO finance (user_id, money, description, date, type) VALUES(?, ?, ?, ?, ?)",
                   user_id, amount, description, date, transaction_type)
        return redirect("/expense")
    else:
        exdatas = db.execute("SELECT * FROM finance WHERE user_id = ? AND type = ? ORDER BY date DESC", user_id, "withdraw")
        total = db.execute("SELECT SUM(money) as sum FROM finance WHERE user_id = ? AND type = ? ORDER BY date DESC", user_id, "withdraw")
        return render_template("expense.html", exdatas = exdatas, total = total)


@app.route("/history", methods=["GET", "POST"])
@login_required
def history():
    """History of all transactions"""
    user_id = session["user_id"]
    if request.method == "POST":
        month = request.form.get("month")
        transactions = db.execute("SELECT * FROM finance WHERE user_id = ? AND strftime('%m', date) = ? ORDER BY date DESC", user_id, month)
        dates = db.execute("SELECT DISTINCT strftime('%m', date) AS month FROM finance WHERE user_id = ? GROUP BY date", user_id)
        totale = db.execute("SELECT SUM(money) as sum FROM finance WHERE user_id = ? AND type = ? AND strftime('%m', date) = ? ORDER BY date DESC", user_id, "deposit", month)
        totals = db.execute("SELECT SUM(money) as sum FROM finance WHERE user_id = ? AND type = ? AND strftime('%m', date) = ? ORDER BY date DESC", user_id, "withdraw", month)
        goal = db.execute("SELECT goal FROM users WHERE id = ?", user_id)
        return render_template("history.html", transactions = transactions, dates = dates, totale = totale, totals = totals, goal = goal)

    else:
        transactions = db.execute("SELECT * FROM finance WHERE user_id = ? ORDER BY date DESC", user_id)
        dates = db.execute("SELECT DISTINCT strftime('%m', date) AS month FROM finance WHERE user_id = ? GROUP BY date", user_id)
        totale = db.execute("SELECT SUM(money) as sum FROM finance WHERE user_id = ? AND type = ? ORDER BY date DESC", user_id, "deposit")
        totals = db.execute("SELECT SUM(money) as sum FROM finance WHERE user_id = ? AND type = ? ORDER BY date DESC", user_id, "withdraw")
        balance = db.execute("SELECT balance FROM users WHERE id = ?", user_id)
        return render_template("history.html", transactions = transactions, dates = dates, totale = totale, totals = totals, balance = balance)


# CITE: cs50 week 9 flask pset finance, boostrap
