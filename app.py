from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import pandas as pd
from functools import wraps
from io import BytesIO
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'

DATABASE = 'loyalty_card.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            session['role'] = user['role']
            if user['role'] == 'admin':
                return redirect('/admin')
            else:
                return redirect('/order')
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
@admin_required
def admin():
    conn = get_db_connection()
    users = conn.execute('SELECT username, role FROM users').fetchall()
    customers = conn.execute('SELECT * FROM customers').fetchall()
    drinks = conn.execute('SELECT * FROM drinks').fetchall()
    conn.close()
    return render_template('admin.html', users=users, customers=customers, drinks=drinks)

@app.route('/add_user', methods=['POST'])
@admin_required
def add_user():
    username = request.form['username']
    password = generate_password_hash(request.form['password'])
    role = request.form['role']
    conn = get_db_connection()
    conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (username, password, role))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/delete_user', methods=['POST'])
@admin_required
def delete_user():
    username = request.form['username']
    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE username = ?', (username,))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/add_customer', methods=['POST'])
@admin_required
def add_customer():
    name = request.form['name']
    unique_id = request.form['unique_id']
    conn = get_db_connection()
    conn.execute('INSERT INTO customers (name, unique_id, total_orders, tokens_earned, tokens_redeemed) VALUES (?, ?, 0, 0, 0)', (name, unique_id))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/delete_customer', methods=['POST'])
@admin_required
def delete_customer():
    customer_id = request.form['customer_id']
    conn = get_db_connection()
    conn.execute('DELETE FROM customers WHERE id = ?', (customer_id,))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/upload_customers', methods=['POST'])
@admin_required
def upload_customers():
    file = request.files['excel_file']
    if file:
        df = pd.read_excel(file)
        conn = get_db_connection()
        for _, row in df.iterrows():
            conn.execute('INSERT INTO customers (name, unique_id, total_orders, tokens_earned, tokens_redeemed) VALUES (?, ?, ?, ?, ?)',
                         (row['name'], str(row['unique_id']).zfill(4), row['total_orders'], row['tokens_earned'], row['tokens_redeemed']))
        conn.commit()
        conn.close()
    return redirect('/admin')

@app.route('/add_drink', methods=['POST'])
@admin_required
def add_drink():
    drink_name = request.form['drink_name']
    conn = get_db_connection()
    conn.execute('INSERT INTO drinks (name) VALUES (?)', (drink_name,))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/delete_drink', methods=['POST'])
@admin_required
def delete_drink():
    drink_id = request.form['drink_id']
    conn = get_db_connection()
    conn.execute('DELETE FROM drinks WHERE id = ?', (drink_id,))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/export_data')
@admin_required
def export_data():
    conn = get_db_connection()
    users_df = pd.read_sql_query('SELECT username, role FROM users', conn)
    customers_df = pd.read_sql_query('SELECT name, unique_id, total_orders, tokens_earned, tokens_redeemed FROM customers', conn)
    customers_df['token_balance'] = customers_df['tokens_earned'] - customers_df['tokens_redeemed']
    conn.close()

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        users_df.to_excel(writer, sheet_name='Users', index=False)
        customers_df.to_excel(writer, sheet_name='Customers', index=False)
    output.seek(0)

    return send_file(output, as_attachment=True, download_name='loyalty_data.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/order')
@login_required
def order():
    conn = get_db_connection()
    drinks = conn.execute('SELECT * FROM drinks').fetchall()
    conn.close()
    return render_template('order.html', drinks=drinks)

@app.route('/get_customers_by_uid')
@login_required
def get_customers_by_uid():
    uid = request.args.get('uid')
    conn = get_db_connection()
    customers = conn.execute('SELECT * FROM customers WHERE unique_id = ?', (uid,)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in customers])

@app.route('/get_customer_summary/<int:customer_id>')
@login_required
def get_customer_summary(customer_id):
    conn = get_db_connection()
    customer = conn.execute('SELECT * FROM customers WHERE id = ?', (customer_id,)).fetchone()
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
    drink = request.form['drink_name']  # ← Correct indentation here
    quantity = int(request.form['quantity'])
    redeem = request.form.get('redeem') == 'on'


    conn = get_db_connection()
    customer = conn.execute('SELECT * FROM customers WHERE id = ?', (customer_id,)).fetchone()
    if not customer:
        conn.close()
        return "Customer not found", 404

    if redeem:
        if customer['tokens_earned'] - customer['tokens_redeemed'] >= quantity:
            conn.execute('UPDATE customers SET tokens_redeemed = tokens_redeemed + ? WHERE id = ?', (quantity, customer_id))
        else:
            conn.close()
            return "Not enough tokens to redeem", 400
    else:
        tokens_earned = quantity // 9
        conn.execute('UPDATE customers SET total_orders = total_orders + ?, tokens_earned = tokens_earned + ? WHERE id = ?',
                     (quantity, tokens_earned, customer_id))

    conn.commit()
    conn.close()
    return redirect('/order')

if __name__ == '__main__':
    app.run(debug=True)
