from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
import os
from werkzeug.utils import secure_filename
import random
from importer import add_recipe_from_url
from flask import flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import re

# MySQL configuration
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_DB = os.getenv('MYSQL_DB', 'recipes')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static')
app.secret_key = 'supersecretkey'  # Needed for session
db = SQLAlchemy(app)

# Recipe model
class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(255), nullable=True, default=None)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

# Helper: get current user
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('You must be logged in to upload recipes.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Username or email already exists.', 'danger')
            return redirect(url_for('register'))
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form['username_or_email']
        password = request.form['password']
        user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Logged in successfully.', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

# Logout route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/')
def home():
    recipes = Recipe.query.all()
    default_image = url_for('static', filename='default.jpg')
    return render_template('home.html', recipes=recipes, default_image=default_image)

@app.route('/type/<recipe_type>')
def recipe_type(recipe_type):
    recipes = Recipe.query.filter_by(type=recipe_type).all()
    default_image = url_for('static', filename='default.jpg')
    return render_template('home.html', recipes=recipes, default_image=default_image)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_recipe():
    if request.method == 'POST':
        name = request.form['name']
        # Collect all ingredient fields
        names = request.form.getlist('ingredient_name')
        qtys = request.form.getlist('ingredient_qty')
        units = request.form.getlist('ingredient_unit')
        ingredients = []
        for n, q, u in zip(names, qtys, units):
            if n.strip():
                part = f"{q.strip()} {u.strip()} {n.strip()}".strip()
                ingredients.append(part)
        ingredients_str = '\n'.join(ingredients)
        instructions = request.form['instructions']
        image_file = request.files.get('image')
        image_url = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(filepath)
            image_url = url_for('static', filename=filename)
        new_recipe = Recipe(name=name, ingredients=ingredients_str, instructions=instructions, image_url=image_url)
        db.session.add(new_recipe)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('add.html')

@app.route('/import_url', methods=['POST'])
def import_url():
    from importer import add_recipe_from_url  # moved import here to avoid circular import
    url = request.form.get('url')
    if not url:
        flash('No URL provided.', 'danger')
        return redirect(url_for('home'))
    try:
        recipe_data = add_recipe_from_url(url)
        if not recipe_data:
            flash('Could not import recipe from the provided URL.', 'danger')
            return redirect(url_for('home'))
        # Show the add page with imported data for user confirmation
        ingredients_list = recipe_data['ingredients']
        return render_template('add.html',
            name=recipe_data['name'],
            ingredients_list=ingredients_list,
            instructions=recipe_data['instructions'],
            image_url=recipe_data['image_url'],
            imported=True
        )
    except Exception as e:
        print(f"Error during import: {e}")
        flash('An error occurred while importing the recipe. Please try again or use a different URL.', 'danger')
        return redirect(url_for('home'))

@app.route('/recipe/<int:recipe_id>')
def view_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    default_image = url_for('static', filename='default.jpg')
    return render_template('view_recipe.html', recipe=recipe, default_image=default_image)

@app.route('/recipe/<int:recipe_id>/edit', methods=['GET', 'POST'])
def edit_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if request.method == 'POST':
        recipe.name = request.form['name']
        names = request.form.getlist('ingredient_name')
        qtys = request.form.getlist('ingredient_qty')
        units = request.form.getlist('ingredient_unit')
        ingredients = []
        for n, q, u in zip(names, qtys, units):
            if n.strip():
                part = f"{q.strip()} {u.strip()} {n.strip()}".strip()
                ingredients.append(part)
        recipe.ingredients = '\n'.join(ingredients)
        recipe.instructions = request.form['instructions']
        image_file = request.files.get('image')
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(filepath)
            recipe.image_url = url_for('static', filename=filename)
        db.session.commit()
        return redirect(url_for('view_recipe', recipe_id=recipe.id))
    default_image = url_for('static', filename='default.jpg')
    # Parse ingredients for the edit form
    def parse_ingredient(ingredient_str):
        match = re.match(r'^\s*(?P<quantity>[\d/.]+)?\s*(?P<unit>[a-zA-Z]+)?\s*(?P<name>.+)$', ingredient_str.strip())
        if match:
            return {
                'quantity': match.group('quantity') or '',
                'unit': match.group('unit') or '',
                'name': match.group('name') or ''
            }
        else:
            return {'quantity': '', 'unit': '', 'name': ingredient_str.strip()}
    ingredients_list = [parse_ingredient(ing) for ing in recipe.ingredients.split('\n') if ing.strip()]
    if not ingredients_list:
        ingredients_list = [{'quantity': '', 'unit': '', 'name': ''}]
    return render_template('edit_recipe.html', recipe=recipe, default_image=default_image, ingredients_list=ingredients_list)

@app.route('/recipe/<int:recipe_id>/delete', methods=['POST'])
def delete_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    confirm = request.form.get('confirm')
    if confirm == 'delete':
        db.session.delete(recipe)
        db.session.commit()
        return redirect(url_for('home'))
    default_image = url_for('static', filename='default.jpg')
    error = 'You must type "delete" to confirm.'
    return render_template('view_recipe.html', recipe=recipe, default_image=default_image, error=error)

@app.route('/cart')
def view_cart():
    cart = session.get('cart', [])
    # Combine duplicate ingredients (simple string match)
    combined = {}
    for item in cart:
        key = item.strip().lower()
        if key:
            if key in combined:
                combined[key]['qty'] += 1
            else:
                combined[key] = {'name': item, 'qty': 1}
    combined_list = list(combined.values())
    return render_template('cart.html', cart=combined_list)

@app.route('/add_to_cart/<int:recipe_id>', methods=['POST'])
def add_to_cart(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    cart = session.get('cart', [])
    # Add all ingredients from this recipe
    for ingredient in recipe.ingredients.split('\n'):
        if ingredient.strip():
            cart.append(ingredient.strip())
    session['cart'] = cart
    return redirect(url_for('view_cart'))

@app.route('/clear_cart', methods=['POST'])
def clear_cart():
    session['cart'] = []
    return redirect(url_for('view_cart'))

@app.route('/random')
def random_recipes():
    recipes = Recipe.query.all()
    selected = random.sample(recipes, min(5, len(recipes))) if recipes else []
    default_image = url_for('static', filename='default.jpg')
    return render_template('random.html', recipes=selected, default_image=default_image)

@app.route('/add_random_to_cart', methods=['POST'])
def add_random_to_cart():
    recipe_ids = request.form.getlist('recipe_id')
    cart = session.get('cart', [])
    for rid in recipe_ids:
        recipe = Recipe.query.get(int(rid))
        if recipe:
            for ingredient in recipe.ingredients.split('\n'):
                if ingredient.strip():
                    cart.append(ingredient.strip())
    session['cart'] = cart
    return redirect(url_for('view_cart'))

@app.route('/ingredients_list')
def ingredients_list():
    # Get all unique ingredients from all recipes
    all_ingredients = set()
    for recipe in Recipe.query.all():
        for ing in recipe.ingredients.split('\n'):
            ing = ing.strip()
            if ing:
                all_ingredients.add(ing)
    return jsonify(sorted(all_ingredients))

if __name__ == '__main__':
    if not os.path.exists('recipes.db'):
        with app.app_context():
            db.create_all()
    app.run(debug=True) 