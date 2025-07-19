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
            return redirect(url_for('admin' if user['role'] == 'admin' else 'order'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/order')
@login_required
def order():
    return render_template('order.html')

@app.route('/get_drinks')
def get_drinks():
    conn = get_db_connection()
    drinks = conn.execute('SELECT * FROM drinks').fetchall()
    conn.close()
    return jsonify([dict(drink) for drink in drinks])

@app.route('/get_customers_by_uid')
def get_customers_by_uid():
    uid = request.args.get('uid')
    conn = get_db_connection()
    customers = conn.execute('SELECT * FROM customers WHERE unique_id = ?', (uid,)).fetchall()
    conn.close()
    return jsonify([dict(c) for c in customers])

@app.route('/get_customer_summary')
def get_customer_summary():
    customer_id = request.args.get('customer_id')
    conn = get_db_connection()
    customer = conn.execute('SELECT * FROM customers WHERE id = ?', (customer_id,)).fetchone()
    conn.close()
    if customer:
        return jsonify({
            'total_orders': customer['total_orders'],
            'tokens_earned': customer['tokens_earned'],
            'tokens_redeemed': customer['tokens_redeemed']
        })
    return jsonify({})

@app.route('/submit_order', methods=['POST'])
def submit_order():
    data = request.form
    customer_id = data.get('customer_id')
    drink = data.get('drink')
    quantity = int(data.get('quantity'))
    redeem = data.get('redeem') == 'yes'

    conn = get_db_connection()
    customer = conn.execute('SELECT * FROM customers WHERE id = ?', (customer_id,)).fetchone()

    if not customer:
        return jsonify({'success': False, 'message': 'Customer not found.'})

    total_orders = customer['total_orders'] + quantity
    tokens_earned = customer['tokens_earned'] + quantity // 9
    tokens_redeemed = customer['tokens_redeemed']

    if redeem:
        available = tokens_earned - tokens_redeemed
        if available < 1:
            conn.close()
            return jsonify({'success': False, 'message': 'Not enough tokens to redeem.'})
        tokens_redeemed += 1

    conn.execute('UPDATE customers SET total_orders = ?, tokens_earned = ?, tokens_redeemed = ? WHERE id = ?',
                 (total_orders, tokens_earned, tokens_redeemed, customer_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Order submitted successfully!'})

@app.route('/admin')
@login_required
def admin():
    if session.get('role') != 'admin':
        return redirect(url_for('order'))
    return render_template('admin.html')
