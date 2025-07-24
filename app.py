# app.py

from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
import pandas as pd
from functools import wraps
from io import BytesIO
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# ---------- Authentication ----------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ---------- Routes ----------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('admin' if user['role'] == 'admin' else 'order'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
@admin_required
def admin():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT username, role FROM users")
    users = cur.fetchall()
    cur.execute("SELECT * FROM customers")
    customers = cur.fetchall()
    cur.execute("SELECT * FROM drinks")
    drinks = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin.html", users=users, customers=customers, drinks=drinks)

# ---------- Admin Functions ----------
@app.route('/add_user', methods=['POST'])
@admin_required
def add_user():
    username = request.form['username']
    password = generate_password_hash(request.form['password'])
    role = request.form['role']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", (username, password, role))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/delete_user', methods=['POST'])
@admin_required
def delete_user():
    username = request.form['username']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username = %s", (username,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/add_customer', methods=['POST'])
@admin_required
def add_customer():
    name = request.form['name']
    uid = request.form['unique_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO customers (name, unique_id, total_orders, tokens_earned, tokens_redeemed) VALUES (%s, %s, 0, 0, 0)", (name, uid))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/delete_customer', methods=['POST'])
@admin_required
def delete_customer():
    customer_id = request.form['customer_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM customers WHERE id = %s", (customer_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/upload_customers', methods=['POST'])
@admin_required
def upload_customers():
    file = request.files['excel_file']
    if file:
        df = pd.read_excel(file)
        df = df.dropna(subset=['name', 'unique_id'])
        conn = get_db_connection()
        cur = conn.cursor()
        for _, row in df.iterrows():
            name = str(row['name']).strip()
            unique_id = str(row['unique_id']).zfill(4)
            total = int(row.get('total_orders', 0) or 0)
            earned = int(row.get('tokens_earned', 0) or 0)
            redeemed = int(row.get('tokens_redeemed', 0) or 0)
            cur.execute("""
                INSERT INTO customers (name, unique_id, total_orders, tokens_earned, tokens_redeemed)
                VALUES (%s, %s, %s, %s, %s)
            """, (name, unique_id, total, earned, redeemed))
        conn.commit()
        cur.close()
        conn.close()
    return redirect(url_for('admin'))

@app.route('/add_drink', methods=['POST'])
@admin_required
def add_drink():
    drink_name = request.form['drink_name']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO drinks (name) VALUES (%s)", (drink_name,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/delete_drink', methods=['POST'])
@admin_required
def delete_drink():
    drink_id = request.form['drink_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM drinks WHERE id = %s", (drink_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/export_data')
@login_required
def export_data():
    if session.get('role') != 'admin':
        return "Access denied", 403

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # --- Export Users ---
        cur.execute("SELECT username, role FROM users")
        user_rows = cur.fetchall()
        user_df = pd.DataFrame(user_rows, columns=[desc[0] for desc in cur.description])

        # --- Export Customers ---
        cur.execute("""
            SELECT name, unique_id, total_orders, tokens_earned, tokens_redeemed,
                   (tokens_earned - tokens_redeemed) AS token_balance
            FROM customers
        """)
        customer_rows = cur.fetchall()
        customer_df = pd.DataFrame(customer_rows, columns=[desc[0] for desc in cur.description])

        # --- Create Excel in-memory ---
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            user_df.to_excel(writer, sheet_name='Users', index=False)
            customer_df.to_excel(writer, sheet_name='Customers', index=False)

        output.seek(0)
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"loyalty_export_{now_str}.xlsx"

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        print("Export error:", e)
        return f"Export failed: {e}", 500

    finally:
        cur.close()
        conn.close()

# ---------- Order Panel ----------
@app.route('/order')
@login_required
def order():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM drinks")
    drinks = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("order.html", drinks=drinks)

@app.route('/get_customers_by_uid')
@login_required
def get_customers_by_uid():
    uid = request.args.get('uid')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers WHERE unique_id = %s", (uid,))
    customers = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(customers)

@app.route('/get_customer_summary/<int:customer_id>')
@login_required
def get_customer_summary(customer_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers WHERE id = %s", (customer_id,))
    customer = cur.fetchone()
    cur.close()
    conn.close()
    if customer:
        balance = customer['tokens_earned'] - customer['tokens_redeemed']
        return jsonify({
            'name': customer['name'],
            'total_orders': customer['total_orders'],
            'tokens_earned': customer['tokens_earned'],
            'tokens_redeemed': customer['tokens_redeemed'],
            'token_balance': balance
        })
    return jsonify({'error': 'Customer not found'}), 404

@app.route('/submit_order', methods=['POST'])
@login_required
def submit_order():
    customer_id = request.form['customer_id']
    drink = request.form['drink_name']
    quantity = int(request.form['quantity'])
    redeem = request.form.get('redeem') == 'on'

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers WHERE id = %s", (customer_id,))
    customer = cur.fetchone()

    if not customer:
        cur.close()
        conn.close()
        return "Customer not found", 404

    if redeem:
        balance = customer['tokens_earned'] - customer['tokens_redeemed']
        if balance >= quantity:
            cur.execute("UPDATE customers SET tokens_redeemed = tokens_redeemed + %s WHERE id = %s", (quantity, customer_id))
        else:
            cur.close()
            conn.close()
            return "Not enough tokens", 400
    else:
        earned = quantity // 9
        cur.execute("""
            UPDATE customers
            SET total_orders = total_orders + %s,
                tokens_earned = tokens_earned + %s
            WHERE id = %s
        """, (quantity, earned, customer_id))

    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('order'))

# ---------- Main ----------
if __name__ == '__main__':
    app.run(debug=True)
