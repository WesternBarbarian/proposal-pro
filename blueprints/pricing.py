import os
import json
import logging
from flask import Blueprint, request, redirect, url_for, flash, session, render_template, jsonify
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import TextAreaField, SubmitField
from ai_helper import generate_price_list, generate_price_list_from_image
from blueprints.auth import require_auth

pricing_bp = Blueprint('pricing', __name__)

class PriceListForm(FlaskForm):
    price_description = TextAreaField('Price Description')
    file = FileField('Upload File', validators=[
        FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'heic'], 'Only PDF, PNG, JPEG, and HEIC files allowed!')
    ])
    submit = SubmitField('Generate Price List')

def load_price_list():
    try:
        with open('price_list.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_price_list(price_list):
    if hasattr(price_list, 'prices'):
        # Convert Items object to dictionary
        price_dict = {item.item: {"unit": item.unit, "price": item.price} for item in price_list.prices}
    else:
        price_dict = price_list

    with open('price_list.json', 'w') as f:
        json.dump(price_dict, f, indent=4)

@pricing_bp.route('/price-list', methods=['GET'])
@require_auth
def price_list():
    form = PriceListForm()
    prices = load_price_list()
    return render_template('price_list.html', prices=prices, form=form, authenticated=True)

@pricing_bp.route('/generate-price-list', methods=['POST'])
@require_auth
def generate_price_list_route():
    try:
        if request.files.get('file') and request.files['file'].filename:
            file = request.files['file']
            temp_path = f"temp_{file.filename}"
            file.save(temp_path)
            try:
                price_items = generate_price_list_from_image(temp_path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        elif request.form.get('price_description'):
            description = request.form.get('price_description')
            price_items = generate_price_list(description)
        else:
            flash('Please provide either a file or price description.', 'error')
            return redirect(url_for('pricing.price_list'))
        
        # Save the generated price list
        save_price_list(price_items)
        
        flash('Price list generated and saved successfully!', 'success')
        return redirect(url_for('pricing.price_list'))
    except Exception as e:
        logging.error(f"Error generating price list: {str(e)}", exc_info=True)
        flash(f'Error generating price list: {str(e)}', 'error')
        return redirect(url_for('pricing.price_list'))

@pricing_bp.route('/delete-price', methods=['POST'])
@require_auth
def delete_price():
    item_name = request.form.get('item')
    if not item_name:
        flash('Item name is required', 'error')
        return redirect(url_for('pricing.price_list'))
    
    price_list = load_price_list()
    if item_name in price_list:
        del price_list[item_name]
        save_price_list(price_list)
        flash('Price deleted successfully', 'success')
    else:
        flash('Item not found', 'error')
    
    return redirect(url_for('pricing.price_list'))

@pricing_bp.route('/add-price', methods=['POST'])
@require_auth
def add_price():
    item = request.form.get('item')
    unit = request.form.get('unit')
    price = request.form.get('price')
    
    if not all([item, unit, price]):
        flash('All fields are required', 'error')
        return redirect(url_for('pricing.price_list'))
    
    try:
        price = float(price)
    except ValueError:
        flash('Price must be a number', 'error')
        return redirect(url_for('pricing.price_list'))
    
    price_list = load_price_list()
    price_list[item] = {"unit": unit, "price": price}
    save_price_list(price_list)
    
    flash('Price added successfully', 'success')
    return redirect(url_for('pricing.price_list'))

@pricing_bp.route('/update-price', methods=['POST'])
@require_auth
def update_price():
    item = request.form.get('item')
    unit = request.form.get('unit')
    price = request.form.get('price')
    
    if not all([item, unit, price]):
        flash('All fields are required', 'error')
        return redirect(url_for('pricing.price_list'))
    
    try:
        price = float(price)
    except ValueError:
        flash('Price must be a number', 'error')
        return redirect(url_for('pricing.price_list'))
    
    price_list = load_price_list()
    
    # Add or update the item
    price_list[item] = {"unit": unit, "price": price}
    save_price_list(price_list)
    
    flash('Price updated successfully', 'success')
    return redirect(url_for('pricing.price_list'))