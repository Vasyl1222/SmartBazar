from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash
from flask import Flask, request, jsonify
import logging
import re
logging.basicConfig(level=logging.DEBUG)




app = Flask(__name__)
app.secret_key = 'my_secret_key' 

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row 
    return conn

def get_products():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE category = 'popular'")
    products = cursor.fetchall()
    conn.close()
    return products

@app.route('/')
def index():
    products = get_products()
    return render_template('index.html', products=products)

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    if 'cart' not in session:
        session['cart'] = []  

    found = False
    for item in session['cart']:
        if item['product_id'] == product_id:
            item['quantity'] += 1 
            found = True
            break
    
    if not found:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM products WHERE id = ?', (product_id,))
        product = cursor.fetchone()
        conn.close()

        if product:
            session['cart'].append({'product_id': product_id, 'quantity': 1})  

    session.modified = True  
    return redirect(url_for('index')) 

@app.route('/all_products', methods=['GET', 'POST'])
def all_products():
    category = request.args.get('category')
    sort_by = request.args.get('sort_by', default='name', type=str)
    sort_order = request.args.get('sort_order', default='asc', type=str)
    search_query = request.args.get('search', '') 

    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM products"
    params = []

    if category:
        query += " WHERE category = ?"
        params.append(category)

    if search_query:
        if 'WHERE' in query:
            query += " AND name LIKE ?"
        else:
            query += " WHERE name LIKE ?"
        params.append('%' + search_query + '%')

    if sort_by == 'price':
        if sort_order == 'asc':
            query += " ORDER BY CAST(price AS REAL) ASC"
        else:
            query += " ORDER BY CAST(price AS REAL) DESC"
    elif sort_by == 'name':
        if sort_order == 'asc':
            query += " ORDER BY name ASC"
        else:
            query += " ORDER BY name DESC"
    
    cursor.execute(query, tuple(params))
    products = cursor.fetchall()
    conn.close()

    return render_template('all_products.html', products=products, search_query=search_query)

@app.route('/update_quantity/<int:product_id>', methods=['POST'])
def update_quantity(product_id):
    increment = request.form.get('increment', type=int, default=0)
    decrement = request.form.get('decrement', type=int, default=0)
    
    if 'cart' in session:
        for item in session['cart']:
            if item['product_id'] == product_id:
                if increment:
                    item['quantity'] += 1
                elif decrement:
                    if item['quantity'] > 1: 
                        item['quantity'] -= 1
                    else:
                        session['cart'].remove(item) 
                break
        session.modified = True  
    return redirect(url_for('cart'))

@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    if 'cart' in session:
        session['cart'] = [item for item in session['cart'] if item['product_id'] != product_id]  
        session.modified = True  
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    cart_items = []
    total_price = 0

    if 'cart' in session:
        conn = get_db_connection()
        cursor = conn.cursor()

        for item in session['cart']:
            cursor.execute('SELECT id, name, price, image FROM products WHERE id = ?', (item['product_id'],))
            product = cursor.fetchone()
            if product:
                price = float(''.join(filter(str.isdigit, product['price'])))

                cart_items.append({
                    'product_id': item['product_id'],
                    'name': product['name'],
                    'price': price,
                    'quantity': item['quantity'],
                    'image': product['image']
                })

                total_price += price * item['quantity']

        conn.close()

    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(''' 
                INSERT INTO users (username, email, password)
                VALUES (?, ?, ?)
            ''', (username, email, hashed_password))

            conn.commit() 
            return redirect(url_for('profile'))

        except sqlite3.IntegrityError:  
            return "Цей логін або email вже використовується."

        finally:
            conn.close()

    return render_template('auth.html')  






@app.route('/login', methods=['POST'])
def login_user():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "message": "Некоректний формат даних"}), 400

    email = data.get('email')
    password = data.get('password')

    logging.debug(f"Login attempt: {email}")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    user = cursor.fetchone()

    if user:
        logging.debug(f"User found: {user}")
        if check_password_hash(user['password'], password):
            logging.debug(f"Password match for: {email}")
            session['email'] = email
            session['username'] = user['username']
            conn.close()
            return jsonify({"success": True, "message": "Успішний вхід"})
        else:
            logging.debug(f"Password mismatch for: {email}")
            conn.close()
            return jsonify({"success": False, "message": "Невірний логін або пароль!"}), 401
    else:
        logging.debug(f"No user found for: {email}")
        conn.close()
        return jsonify({"success": False, "message": "Невірний логін або пароль!"}), 401




@app.route('/order_form')
def order_form():
    cart_items = []
    total_price = 0

    if 'cart' in session:
        try:
            conn = get_db_connection()
            if conn is None:
                raise Exception("Не вдалося підключитися до бази даних")

            cursor = conn.cursor()

            for item in session['cart']:
                cursor.execute('SELECT id, name, price, image FROM products WHERE id = ?', (item['product_id'],))
                product = cursor.fetchone()
                if product:
                    price = float(''.join(filter(str.isdigit, product['price'])))

                    cart_items.append({
                        'product_id': item['product_id'],
                        'name': product['name'],
                        'price': price,
                        'quantity': item['quantity'],
                        'image': product['image']
                    })

                    total_price += price * item['quantity']

            conn.close()

        except Exception as e:
            print(f"Помилка при обробці замовлення: {e}")
            return "Сталася помилка при обробці вашого замовлення, спробуйте ще раз."

    return render_template('order_form.html', cart_items=cart_items, total_price=total_price)

@app.route('/submit_order', methods=['POST'])
def submit_order():
    name = request.form.get('name')
    phone = request.form.get('phone')
    address = request.form.get('address')
    email = request.form.get('email')  
    comments = request.form.get('comments')
    promo_code = request.form.get('promo_code')  

    if 'cart' not in session or len(session['cart']) == 0:
        flash("Ваша корзина пуста. Додайте товари перед оформленням замовлення.")
        return redirect(url_for('cart'))

    print("Товари в кошику:", session['cart'])  

    total_price = 0
    with get_db_connection() as conn:
        cursor = conn.cursor()

        for item in session['cart']:
            cursor.execute('SELECT price FROM products WHERE id = ?', (item['product_id'],))
            product = cursor.fetchone()
            if product:
                product_price = ''.join(filter(str.isdigit, product['price']))  
                try:
                    product_price = float(product_price) 
                except ValueError:
                    product_price = 0  
                total_price += product_price * item['quantity']

        cursor.execute(''' 
            INSERT INTO orders (name, phone, address, email, comments, promo_code, total_price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, phone, address, email, comments, promo_code, total_price))

        order_id = cursor.lastrowid  
        conn.commit()  

        for item in session['cart']:
            cursor.execute('SELECT name, price FROM products WHERE id = ?', (item['product_id'],))
            product = cursor.fetchone()

            if product:
                product_name = product['name']
                product_price = ''.join(filter(str.isdigit, product['price']))  
                try:
                    product_price = float(product_price)  
                except ValueError:
                    product_price = 0 
                quantity = item['quantity']
                total_item_price = product_price * quantity

                print(f"Товар: {product_name}, ціна: {product_price}, кількість: {quantity}, загальна ціна: {total_item_price}")

                cursor.execute(''' 
                    INSERT INTO order_items (order_id, product_name, product_price, quantity, total_price)
                    VALUES (?, ?, ?, ?, ?)
                ''', (order_id, product_name, product_price, quantity, total_item_price))
            else:
                print(f"Товар не знайдений для ID: {item['product_id']}")

        conn.commit() 

    session.pop('cart', None)

    flash("Ваше замовлення успішно оформлене.")
    return redirect(url_for('index'))




@app.route('/admin')
def admin_panel():
    conn = get_db_connection()

    users_query = '''
        SELECT 
            id, 
            username, 
            email, 
            password, 
            phone
        FROM 
            users;
        '''

    users = conn.execute(users_query).fetchall()

    orders_query = '''
        SELECT 
            id AS order_id, 
            phone, 
            name, 
            address,
            comments, 
            email, 
            promo_code, 
            total_price, 
            created_at
        FROM 
            orders;
        '''

    orders = conn.execute(orders_query).fetchall()

    order_items_query = '''
        SELECT 
            id, 
            order_id, 
            product_name, 
            product_price, 
            quantity, 
            total_price, 
            created_at
        FROM 
            order_items;
    '''
    order_items = conn.execute(order_items_query).fetchall()

    reviews_query = '''
            SELECT 
                id, 
                name, 
                email, 
                review,
                created_at
            FROM 
                reviews;
        '''

    reviews = conn.execute(reviews_query).fetchall()

    conn.close()

    return render_template('admin.html', users=users, orders=orders, order_items=order_items, reviews=reviews)

@app.route('/logout')
def logout():
    session.pop('user_id', None)  
    return redirect(url_for('index'))


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()  
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    phone = data.get('phone', '')

    if not all([username, email, password]):
        return jsonify({'success': False, 'message': 'Всі обов\'язкові поля повинні бути заповнені'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    existing_user = cursor.fetchone()

    if existing_user:
        conn.close()
        return jsonify({'success': False, 'message': 'Користувач з таким email вже існує'}), 400

    hashed_password = generate_password_hash(password)

    cursor.execute(''' 
        INSERT INTO users (username, email, password, phone) 
        VALUES (?, ?, ?, ?)
    ''', (username, email, hashed_password, phone))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Реєстрація успішна'}), 201


from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
import os

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'email' not in session:
        return redirect(url_for('login'))

    email = session['email']

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user_data = cursor.fetchone()

        error = None

        if request.method == 'POST':
            new_username = request.form['username']
            new_email = request.form['email']
            new_profile_picture = request.files.get('profile_picture')

            if new_username == user_data['username'] and new_email == user_data['email']:
                error = "Немає змін у даних профілю!"
                return render_template('profile.html', user_data=user_data, error=error)

            cursor.execute('SELECT * FROM users WHERE email = ?', (new_email,))
            existing_user = cursor.fetchone()

            if existing_user and existing_user['email'] != user_data['email']:
                error = "Цей email вже зареєстрований!"
                return render_template('profile.html', user_data=user_data, error=error)

            if new_username != user_data['username'] or new_email != user_data['email']:
                cursor.execute('UPDATE users SET username = ?, email = ? WHERE email = ?',
                               (new_username, new_email, email))
                conn.commit()

            if new_profile_picture and allowed_file(new_profile_picture.filename):
                filename = secure_filename(new_profile_picture.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                new_profile_picture.save(filepath)

                cursor.execute('UPDATE users SET profile_picture = ? WHERE email = ?', (filename, new_email))
                conn.commit()

            session['username'] = new_username
            session['email'] = new_email

            return redirect(url_for('profile'))

        cursor.execute('SELECT * FROM orders WHERE email = ?', (email,))
        orders = cursor.fetchall()

        order_items = []
        for order in orders:
            order_id = order['id']
            cursor.execute('SELECT * FROM order_items WHERE order_id = ?', (order_id,))
            items = cursor.fetchall()

            for item in items:
                order_items.append({
                    'order_id': order_id,
                    'product_name': item['product_name'],
                    'product_price': item['product_price'],
                    'quantity': item['quantity'],
                    'total_price': item['total_price']
                })

        cursor.execute('SELECT * FROM reviews WHERE email = ?', (email,))
        reviews = cursor.fetchall()

    return render_template('profile.html', user_data=user_data, orders=orders, order_items=order_items, reviews=reviews, error=error)

def get_product_by_id(product_id):
    conn = sqlite3.connect('your_database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()  

    conn.close()
    return product




@app.route('/reviews', methods=['GET', 'POST'])
def reviews():
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        review = request.form.get('review')

        if not name or not email or not review:
            error = "Всі поля мають бути заповнені!"
            reviews = conn.execute('SELECT * FROM reviews').fetchall()
            conn.close()
            return render_template('reviews.html', reviews=reviews, error=error)

        conn.execute('INSERT INTO reviews (name, email, review) VALUES (?, ?, ?)', 
                     (name, email, review))
        conn.commit()
        return render_template('reviews.html', success_message="Дякуємо за відгук!")  

    reviews = conn.execute('SELECT * FROM reviews').fetchall()
    conn.close()
    return render_template('reviews.html', reviews=reviews)


@app.route('/api/reviews', methods=['GET', 'POST'])
def api_reviews():
    try:
        conn = get_db_connection()

        if request.method == 'POST':
            data = request.get_json()

            name = data.get('name')
            email = data.get('email')
            review = data.get('review')

            if not name or not email or not review:
                return jsonify({"success": False, "message": "Всі поля мають бути заповнені!"}), 400

            conn.execute('INSERT INTO reviews (name, email, review) VALUES (?, ?, ?)', 
                         (name, email, review))
            conn.commit()
            conn.close()

            return jsonify({"success": True, "message": "Дякуємо за відгук!"}), 201

        elif request.method == 'GET':
            reviews = conn.execute('SELECT * FROM reviews').fetchall()
            conn.close()

            reviews_list = [{"id": review[0], "name": review[1], "email": review[2], "review": review[3]} 
                            for review in reviews]

            return jsonify({"success": True, "reviews": reviews_list})

    except Exception as e:
        conn.close()
        return jsonify({"success": False, "message": "Виникла помилка при обробці запиту", "error": str(e)}), 500


@app.route('/api/add_to_cart/<int:product_id>', methods=['POST'])
def api_add_to_cart(product_id):
    if 'cart' not in session:
        session['cart'] = []  

    found = False
    for item in session['cart']:
        if item['product_id'] == product_id:
            item['quantity'] += 1  
            found = True
            break
    
    if not found:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM products WHERE id = ?', (product_id,))
        product = cursor.fetchone()
        conn.close()

        if product:
            session['cart'].append({'product_id': product_id, 'quantity': 1})  

    session.modified = True  
    return jsonify({"success": True, "message": "Товар додано в кошик"}), 200 

@app.route('/api/cart', methods=['GET'])
def get_cart():
    try:
        cart_items = []
        total_price = 0

        if 'cart' in session:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                for item in session['cart']:
                    cursor.execute('SELECT id, name, price, image FROM products WHERE id = ?', (item['product_id'],))
                    product = cursor.fetchone()
                    if product:
                        try:
                            price = float(''.join(filter(str.isdigit, product['price'])))
                        except ValueError as e:
                            return jsonify({
                                "success": False,
                                "message": f"Помилка обробки ціни для продукту {product['name']}",
                                "error": str(e)
                            }), 500

                        cart_items.append({
                            'product_id': item['product_id'],
                            'name': product['name'],
                            'price': price,
                            'quantity': item['quantity'],
                            'image': product['image']
                        })

                        total_price += price * item['quantity']

            except Exception as db_error:
                return jsonify({
                    "success": False,
                    "message": "Помилка роботи з базою даних",
                    "error": str(db_error)
                }), 500
            finally:
                conn.close()

        return jsonify({'cart_items': cart_items, 'total_price': total_price}), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Виникла помилка під час отримання кошика",
            "error": str(e)
        }), 500

@app.route('/api/update_quantity/<int:product_id>', methods=['POST'])
def api_update_quantity(product_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Немає даних у запиті"}), 400

        quantity = data.get('quantity')
        if quantity is None:
            return jsonify({"success": False, "message": "Кількість не вказана"}), 400

        if not isinstance(quantity, int) or quantity < 0:
            return jsonify({"success": False, "message": "Кількість повинна бути додатнім числом"}), 400

        print(f"Request data: {data}")
        print(f"Current cart before update: {session.get('cart', [])}")

        if 'cart' in session:
            found = False
            for item in session['cart']:
                if item['product_id'] == product_id:
                    found = True
                    if quantity > 0:
                        item['quantity'] = quantity
                    else:
                        session['cart'].remove(item)
                    break

            if not found:
                return jsonify({"success": False, "message": "Товар не знайдено в кошику"}), 404

            session.modified = True
            print(f"Updated cart: {session['cart']}")
            return jsonify({"success": True, "message": "Кількість оновлено"}), 200

        return jsonify({"success": False, "message": "Кошик порожній"}), 404

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            "success": False,
            "message": "Виникла помилка під час оновлення кількості товару",
            "error": str(e)
        }), 500

@app.route('/api/remove_from_cart/<int:product_id>', methods=['DELETE'])
def api_remove_from_cart(product_id):
    try:
        if 'cart' in session:
            initial_length = len(session['cart'])

            session['cart'] = [item for item in session['cart'] if item['product_id'] != product_id]

            if len(session['cart']) < initial_length:
                session.modified = True 
                return jsonify({"success": True, "message": "Товар видалено з кошика"}), 200
            else:
                return jsonify({"success": False, "message": "Товар не знайдено в кошику"}), 404

        return jsonify({"success": False, "message": "Кошик порожній"}), 404

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            "success": False,
            "message": "Виникла помилка під час видалення товару з кошика",
            "error": str(e)
        }), 500

@app.route('/auth/api/register', methods=['POST'])
def api_register():
    try:
        data = request.get_json()  
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        phone = data.get('phone', '')

        if not all([username, email, password]):
            return jsonify({'success': False, 'message': 'Всі обов\'язкові поля повинні бути заповнені'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            return jsonify({'success': False, 'message': 'Користувач з таким email вже існує'}), 400

        hashed_password = generate_password_hash(password)

        cursor.execute(''' 
            INSERT INTO users (username, email, password, phone) 
            VALUES (?, ?, ?, ?)
        ''', (username, email, hashed_password, phone))
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Реєстрація успішна'}), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Виникла помилка під час реєстрації',
            'error': str(e)
        }), 500

@app.route('/auth/api/login', methods=['POST'])
def api_login_user():
    try:
        data = request.get_json()
        logging.debug(f"Received data: {data}")

        if not data:
            return jsonify({"success": False, "message": "Некоректний формат даних"}), 400

        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({"success": False, "message": "Email та пароль є обов'язковими"}), 400

        logging.debug(f"Login attempt: {email}")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()

        if user:
            logging.debug(f"User found: {user}")
            if check_password_hash(user['password'], password):
                logging.debug(f"Password match for: {email}")
                session['email'] = email
                session['username'] = user['username']
                conn.close()
                return jsonify({"success": True, "message": "Успішний вхід"}), 200
            else:
                logging.debug(f"Password mismatch for: {email}")
                conn.close()
                return jsonify({"success": False, "message": "Невірний логін або пароль!"}), 401
        else:
            logging.debug(f"No user found for: {email}")
            conn.close()
            return jsonify({"success": False, "message": "Невірний логін або пароль!"}), 401

    except Exception as e:
        logging.error(f"Error during login: {str(e)}")
        return jsonify({"success": False, "message": "Виникла помилка під час входу", "error": str(e)}), 500
    


@app.route('/api/submit_order', methods=['POST'])
def api_submit_order():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "message": "Не вдалося отримати дані у форматі JSON"}), 400

        name = data.get('name')
        phone = data.get('phone')
        address = data.get('address')
        email = data.get('email')
        comments = data.get('comments')

        if not name or len(name) < 2:
            return jsonify({"success": False, "message": "Некоректне ім'я. Воно має містити щонайменше 2 символи."}), 400
        
        phone_regex = r'^\+380\d{9}$'
        if not phone or not re.match(phone_regex, phone):
           return jsonify({"success": False, "message": "Некоректний номер телефону. Він має починатися з '+380' і містити 12 цифр після знаку '+'."}), 400

        
        if not address or len(address) < 5:
            return jsonify({"success": False, "message": "Адреса має бути щонайменше 5 символів."}), 400
        
        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        if not email or not re.match(email_regex, email):
            return jsonify({"success": False, "message": "Некоректна адреса електронної пошти."}), 400

        if 'cart' not in session or len(session['cart']) == 0:
            return jsonify({"success": False, "message": "Ваша корзина пуста. Додайте товари перед оформленням замовлення."}), 400

        total_price = 0
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for item in session['cart']:
                cursor.execute('SELECT price FROM products WHERE id = ?', (item['product_id'],))
                product = cursor.fetchone()
                if product:
                    product_price = float(product['price'])
                    total_price += product_price * item['quantity']

        return jsonify({
            "success": True,
            "message": "Замовлення успішно оформлено!",
            "total_price": total_price
        }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Виникла помилка при оформленні замовлення",
            "error": str(e)
        }), 500


@app.route('/api/products', methods=['GET'])
def api_get_products():
    category = request.args.get('category')
    sort_by = request.args.get('sort_by', default='name', type=str)
    sort_order = request.args.get('sort_order', default='asc', type=str)
    search_query = request.args.get('search', '')  

    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM products"
    params = []

    if category:
        query += " WHERE category = ?"
        params.append(category)

    if search_query:
        if 'WHERE' in query:
            query += " AND name LIKE ?"
        else:
            query += " WHERE name LIKE ?"
        params.append('%' + search_query + '%')

    if sort_by == 'price':
        if sort_order == 'asc':
            query += " ORDER BY CAST(price AS REAL) ASC"
        else:
            query += " ORDER BY CAST(price AS REAL) DESC"
    elif sort_by == 'name':
        if sort_order == 'asc':
            query += " ORDER BY name ASC"
        else:
            query += " ORDER BY name DESC"
    
    cursor.execute(query, tuple(params))
    products = cursor.fetchall()
    conn.close()

    products_list = [{
        "id": product[0],         
        "name": product[1],       
        "price": product[2],      
        "category": product[3],   
        "description": product[4], 
        "image_url": product[5]   
    } for product in products]
    
    return jsonify(products_list)

@app.route('/api/submit_order/<int:order_id>', methods=['GET'])
def api_get_order(order_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        order = cursor.fetchone()

        conn.close()

        if not order:
            return jsonify({"success": False, "message": "Замовлення не знайдено"}), 404

        order_data = {
            "id": order[0],           
            "name": order[1],         
            "phone": order[2],        
            "address": order[3],      
            "email": order[4],        
            "comments": order[5],     
            "total_price": order[6]   
        }

        return jsonify({"success": True, "order": order_data})

    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Виникла помилка при отриманні замовлення",
            "error": str(e)
        }), 500


if __name__ == '__main__':
    app.run(debug=True)  