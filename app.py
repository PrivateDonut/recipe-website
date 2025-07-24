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
from dotenv import load_dotenv
load_dotenv()
import click

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

# Ingredient model
class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.String(32), nullable=True)
    unit = db.Column(db.String(32), nullable=True)

# Recipe model
class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(255), nullable=True, default=None)
    ingredients = db.relationship('Ingredient', backref='recipe', cascade='all, delete-orphan')
    # Legacy column for migration - will be removed after migration
    legacy_ingredients = db.Column('ingredients', db.Text, nullable=True)

@app.route('/')
def home():
    recipes = Recipe.query.all()
    default_image = url_for('static', filename='default.jpg')
    return render_template('home.html', recipes=recipes, default_image=default_image)

# Remove or comment out this route unless you add a 'type' column to Recipe
# @app.route('/type/<recipe_type>')
# def recipe_type(recipe_type):
#     recipes = Recipe.query.filter_by(type=recipe_type).all()
#     default_image = url_for('static', filename='default.jpg')
#     return render_template('home.html', recipes=recipes, default_image=default_image)

@app.route('/add', methods=['GET', 'POST'])
def add_recipe():
    if request.method == 'POST':
        name = request.form['name']
        instructions = request.form['instructions']
        image_file = request.files.get('image')
        image_url = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(filepath)
            image_url = url_for('static', filename=filename)
        new_recipe = Recipe(name=name, instructions=instructions, image_url=image_url)
        db.session.add(new_recipe)
        db.session.flush()  # Get new_recipe.id before commit

        # Add ingredients
        names = request.form.getlist('ingredient_name')
        qtys = request.form.getlist('ingredient_qty')
        units = request.form.getlist('ingredient_unit')
        for n, q, u in zip(names, qtys, units):
            if n.strip():
                ing = Ingredient(recipe_id=new_recipe.id, name=n.strip(), quantity=q.strip(), unit=u.strip())
                db.session.add(ing)
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
        recipe.instructions = request.form['instructions']
        image_file = request.files.get('image')
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(filepath)
            recipe.image_url = url_for('static', filename=filename)
        # Remove old ingredients
        Ingredient.query.filter_by(recipe_id=recipe.id).delete()
        # Add new ingredients
        names = request.form.getlist('ingredient_name')
        qtys = request.form.getlist('ingredient_qty')
        units = request.form.getlist('ingredient_unit')
        for n, q, u in zip(names, qtys, units):
            if n.strip():
                ing = Ingredient(recipe_id=recipe.id, name=n.strip(), quantity=q.strip(), unit=u.strip())
                db.session.add(ing)
        db.session.commit()
        return redirect(url_for('view_recipe', recipe_id=recipe.id))
    default_image = url_for('static', filename='default.jpg')
    ingredients_list = [{'name': ing.name, 'quantity': ing.quantity, 'unit': ing.unit} for ing in recipe.ingredients]
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
    # Add all ingredients from this recipe using the new relationship
    for ingredient in recipe.ingredients:
        if ingredient.name:
            # Format ingredient string for cart
            ingredient_str = f"{ingredient.quantity} {ingredient.unit} {ingredient.name}".strip()
            cart.append(ingredient_str)
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
            # Add ingredients using the new relationship
            for ingredient in recipe.ingredients:
                if ingredient.name:
                    ingredient_str = f"{ingredient.quantity} {ingredient.unit} {ingredient.name}".strip()
                    cart.append(ingredient_str)
    session['cart'] = cart
    return redirect(url_for('view_cart'))

@app.route('/ingredients_list')
def ingredients_list():
    # Get all unique ingredients from all recipes using the new relationship
    all_ingredients = set()
    for recipe in Recipe.query.all():
        for ing in recipe.ingredients:
            if ing.name:
                all_ingredients.add(ing.name)
    return jsonify(sorted(all_ingredients))

def parse_ingredient(ingredient_str):
    known_units = {'lbs', 'oz', 'g', 'kg', 'cups', 'tbsp', 'tsp', 'pieces', 'cloves', 'slices'}
    parts = ingredient_str.strip().split()
    if not parts:
        return {'quantity': '', 'unit': '', 'name': ''}
    if len(parts) == 1:
        return {'quantity': '', 'unit': '', 'name': parts[0]}
    if re.match(r'^[\d/.]+$', parts[0]):
        quantity = parts[0]
        if len(parts) > 2 and parts[1].lower() in known_units:
            unit = parts[1]
            name = ' '.join(parts[2:])
        elif len(parts) > 1:
            unit = ''
            name = ' '.join(parts[1:])
        else:
            unit = ''
            name = ''
        return {'quantity': quantity, 'unit': unit, 'name': name}
    if parts[0].lower() in known_units:
        return {'quantity': '', 'unit': parts[0], 'name': ' '.join(parts[1:])}
    return {'quantity': '', 'unit': '', 'name': ' '.join(parts)}

def migrate_ingredients():
    """Migrate ingredients from legacy text column to normalized Ingredient table"""
    migrated_recipes = 0
    total_ingredients = 0
    
    for recipe in Recipe.query.all():
        # Skip if already migrated (has Ingredient children)
        if Ingredient.query.filter_by(recipe_id=recipe.id).count() > 0:
            continue
            
        # Check if recipe has legacy ingredients to migrate
        if not recipe.legacy_ingredients:
            continue
            
        # Parse and migrate ingredients
        for line in recipe.legacy_ingredients.splitlines():
            line = line.strip()
            if line:
                parsed = parse_ingredient(line)
                ing = Ingredient(
                    recipe_id=recipe.id,
                    name=parsed['name'],
                    quantity=parsed['quantity'],
                    unit=parsed['unit']
                )
                db.session.add(ing)
                total_ingredients += 1
        
        migrated_recipes += 1
    
    db.session.commit()
    print(f'Migration complete! {migrated_recipes} recipes migrated, {total_ingredients} ingredients created.')

@app.cli.command('migrate-ingredients')
def migrate_ingredients_command():
    """Migrate ingredients from legacy text column to normalized table"""
    with app.app_context():
        migrate_ingredients()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 