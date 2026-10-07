from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import secrets
from functools import wraps
from pathlib import Path

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DB_PATH = Path(__file__).with_name("canteen.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'student'
    );

    CREATE TABLE IF NOT EXISTS menu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        available INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_name TEXT NOT NULL,
        total REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        payment_status TEXT NOT NULL DEFAULT 'Pending',
        order_code TEXT UNIQUE NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        menu_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id),
        FOREIGN KEY(menu_id) REFERENCES menu(id)
    );
    """)
    # Seed demo accounts/menu only when absent.
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO users(name,email,password,role) VALUES (?,?,?,?)",
            ("Administrator", "admin@canteen.local", "admin123", "admin")
        )
        conn.execute(
            "INSERT INTO users(name,email,password,role) VALUES (?,?,?,?)",
            ("Demo Student", "student@canteen.local", "student123", "student")
        )

    if conn.execute("SELECT COUNT(*) FROM menu").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO menu(name,description,price) VALUES (?,?,?)",
            [
                ("Veg Burger", "Fresh vegetable burger", 50),
                ("Masala Dosa", "Crispy dosa with chutney", 60),
                ("Veg Pizza", "Cheesy vegetable pizza", 120),
                ("Sandwich", "Grilled vegetable sandwich", 45),
                ("French Fries", "Crispy salted fries", 40),
                ("Tea", "Hot milk tea", 15),
            ]
        )
    conn.commit()
    conn.close()

def login_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login", next=request.path))
            if role and session.get("role") != role:
                flash("Access denied.", "error")
                return redirect(url_for("menu"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?", (email, password)
        ).fetchone()
        conn.close()
        if not user:
            flash("Invalid email or password.", "error")
            return render_template("login.html")
        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("menu"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/menu")
@login_required()
def menu():
    conn = get_db()
    items = conn.execute("SELECT * FROM menu WHERE available=1 ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("menu.html", items=items)

@app.route("/cart")
@login_required()
def cart():
    cart = session.get("cart", {})
    ids = [int(x) for x in cart.keys()]
    items = []
    total = 0
    if ids:
        conn = get_db()
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT * FROM menu WHERE id IN ({placeholders})", ids
        ).fetchall()
        conn.close()
        by_id = {str(r["id"]): r for r in rows}
        for item_id, qty in cart.items():
            if item_id in by_id:
                row = by_id[item_id]
                subtotal = row["price"] * int(qty)
                items.append({"item": row, "quantity": int(qty), "subtotal": subtotal})
                total += subtotal
    return render_template("cart.html", items=items, total=total)

@app.post("/cart/add/<int:item_id>")
@login_required()
def add_to_cart(item_id):
    conn = get_db()
    item = conn.execute("SELECT * FROM menu WHERE id=? AND available=1", (item_id,)).fetchone()
    conn.close()
    if not item:
        flash("Food item is unavailable.", "error")
        return redirect(url_for("menu"))
    cart = session.get("cart", {})
    key = str(item_id)
    cart[key] = int(cart.get(key, 0)) + 1
    session["cart"] = cart
    flash(f"{item['name']} added to cart.", "success")
    return redirect(url_for("menu"))

@app.post("/cart/update")
@login_required()
def update_cart():
    cart = session.get("cart", {})
    for key in list(cart.keys()):
        value = request.form.get(f"qty_{key}", "0")
        try:
            qty = int(value)
        except ValueError:
            qty = 0
        if qty <= 0:
            cart.pop(key, None)
        else:
            cart[key] = min(qty, 20)
    session["cart"] = cart
    return redirect(url_for("cart"))

@app.route("/checkout", methods=["GET", "POST"])
@login_required()
def checkout():
    cart = session.get("cart", {})
    if not cart:
        flash("Your cart is empty.", "error")
        return redirect(url_for("menu"))

    conn = get_db()
    ids = [int(x) for x in cart]
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(f"SELECT * FROM menu WHERE id IN ({placeholders})", ids).fetchall()
    conn.close()
    by_id = {str(r["id"]): r for r in rows}
    total = sum(by_id[k]["price"] * int(v) for k, v in cart.items() if k in by_id)

    if request.method == "POST":
        # Demo payment: this records a successful mock payment.
        payment_method = request.form.get("payment_method", "Demo Payment")
        order_code = secrets.token_hex(3).upper()
        conn = get_db()
        cur = conn.execute(
            """INSERT INTO orders(student_name,total,status,payment_status,order_code)
               VALUES (?,?,?,?,?)""",
            (session["name"], total, "Pending", "Paid", order_code)
        )
        order_id = cur.lastrowid
        for key, qty in cart.items():
            if key in by_id:
                conn.execute(
                    "INSERT INTO order_items(order_id,menu_id,quantity,price) VALUES (?,?,?,?)",
                    (order_id, int(key), int(qty), by_id[key]["price"])
                )
        conn.commit()
        conn.close()
        session["cart"] = {}
        session["last_order"] = order_id
        return redirect(url_for("order_success", order_id=order_id))
    return render_template("checkout.html", total=total)

@app.route("/order/<int:order_id>/success")
@login_required()
def order_success(order_id):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    items = conn.execute("""
        SELECT oi.quantity, oi.price, m.name
        FROM order_items oi JOIN menu m ON m.id=oi.menu_id
        WHERE oi.order_id=?
    """, (order_id,)).fetchall()
    conn.close()
    if not order:
        return "Order not found", 404
    if session.get("role") != "admin" and order["student_name"] != session.get("name"):
        return "Access denied", 403
    return render_template("order_success.html", order=order, items=items)

@app.route("/my-orders")
@login_required()
def my_orders():
    conn = get_db()
    orders = conn.execute(
        "SELECT * FROM orders WHERE student_name=? ORDER BY id DESC", (session["name"],)
    ).fetchall()
    conn.close()
    return render_template("my_orders.html", orders=orders)

@app.route("/admin")
@login_required("admin")
def admin_dashboard():
    conn = get_db()
    orders = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    menu_items = conn.execute("SELECT * FROM menu ORDER BY id DESC").fetchall()

    order_items_rows = conn.execute("""
        SELECT oi.order_id, oi.quantity, oi.price, m.name
        FROM order_items oi
        JOIN menu m ON m.id = oi.menu_id
        ORDER BY oi.id ASC
    """).fetchall()

    items_by_order = {}
    for item in order_items_rows:
        items_by_order.setdefault(item["order_id"], []).append(item)

    conn.close()
    return render_template(
        "admin_dashboard.html",
        orders=orders,
        menu_items=menu_items,
        items_by_order=items_by_order
    )

@app.post("/admin/order/<int:order_id>/status")
@login_required("admin")
def update_order_status(order_id):
    status = request.form.get("status")
    if status not in {"Pending", "Preparing", "Ready", "Collected"}:
        flash("Invalid status.", "error")
        return redirect(url_for("admin_dashboard"))
    conn = get_db()
    conn.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit()
    conn.close()
    flash("Order status updated.", "success")
    return redirect(url_for("admin_dashboard"))

@app.post("/admin/menu/add")
@login_required("admin")
def add_menu():
    name = request.form["name"].strip()
    description = request.form.get("description", "").strip()
    try:
        price = float(request.form["price"])
    except ValueError:
        price = -1
    if not name or price < 0:
        flash("Enter a valid food name and price.", "error")
        return redirect(url_for("admin_dashboard"))
    conn = get_db()
    conn.execute("INSERT INTO menu(name,description,price) VALUES (?,?,?)",
                 (name, description, price))
    conn.commit()
    conn.close()
    flash("Menu item added.", "success")
    return redirect(url_for("admin_dashboard"))

@app.post("/admin/menu/<int:item_id>/toggle")
@login_required("admin")
def toggle_menu(item_id):
    conn = get_db()
    conn.execute("UPDATE menu SET available=1-available WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))

@app.post("/admin/collect/<int:order_id>")
@login_required("admin")
def collect_order(order_id):
    code = request.form.get("order_code", "").strip().upper()
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if order and order["order_code"] == code and order["status"] == "Ready":
        conn.execute("UPDATE orders SET status='Collected' WHERE id=?", (order_id,))
        conn.commit()
        flash("Order collected successfully.", "success")
    else:
        flash("Order code is incorrect or the order is not ready.", "error")
    conn.close()
    return redirect(url_for("admin_dashboard"))

@app.route("/qr")
def qr_info():
    # This page is the destination represented by the canteen QR code.
    return redirect(url_for("index"))

init_db()
if __name__ == "__main__":
     app.run(debug=True)
