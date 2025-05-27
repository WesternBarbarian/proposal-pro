
import os
import json
import logging
from flask import Blueprint, request, redirect, url_for, flash, session, render_template, jsonify
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import TextAreaField, SubmitField
from ai_helper import generate_price_list, generate_price_list_from_image
from blueprints.auth import require_auth
from db.price_lists import get_price_list, save_price_list

pricing_bp = Blueprint('pricing', __name__)

class PriceListForm(FlaskForm):
    price_description = TextAreaField('Price Description')
    file = FileField('Upload File', validators=[
        FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'heic'], 'Only PDF, PNG, JPEG, and HEIC files allowed!')
    ])
    submit = SubmitField('Generate Price List')

@pricing_bp.route('/price-list', methods=['GET'])
@require_auth
def price_list():
    form = PriceListForm()
    # Get user's email from session
    user_email = session.get('user_email')
    # Load price list from database for this tenant
    prices = get_price_list(user_email)
    return render_template('price_list.html', prices=prices, form=form, authenticated=True)

@pricing_bp.route('/generate-price-list', methods=['POST'])
@require_auth
def generate_price_list_route():
    try:
        # Get user's email from session
        user_email = session.get('user_email')
        if not user_email:
            flash('User session expired. Please log in again.', 'error')
            return redirect(url_for('auth.login'))

        # Handle file upload or text input
        if request.files.get('file') and request.files['file'].filename:
            # Handle file upload
            file = request.files['file']
            temp_path = f"temp_{file.filename}"
            file.save(temp_path)
            try:
                items = generate_price_list_from_image(temp_path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        elif request.form.get('price_description'):
            # Handle text input
            price_description = request.form.get('price_description')
            items = generate_price_list(price_description)
        else:
            flash('Please provide either a file or price description.', 'error')
            return redirect(url_for('pricing.price_list'))

        # Convert AI response to dictionary format for database storage
        price_list_dict = {}
        for item in items.prices:
            price_list_dict[item.item] = {
                "unit": item.unit,
                "price": item.price
            }

        # Save to database
        if save_price_list(user_email, price_list_dict):
            flash('Price list generated and saved successfully!', 'success')
        else:
            flash('Price list generated but failed to save to database.', 'warning')

        return redirect(url_for('pricing.price_list'))

    except Exception as e:
def generate_price_list_route():
    try:
        user_email = session.get('user_email')
        
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
        
        # Convert Items object to dictionary if needed
        if hasattr(price_items, 'prices'):
            price_dict = {item.item: {"unit": item.unit, "price": item.price} for item in price_items.prices}
        else:
            price_dict = price_items
            
        # Save the generated price list to database
        save_result = save_price_list(user_email, price_dict)
        
        if save_result:
            flash('Price list generated and saved successfully!', 'success')
        else:
            flash('Error saving price list to database.', 'error')
            
        return redirect(url_for('pricing.price_list'))
    except Exception as e:
        logging.error(f"Error generating price list: {str(e)}", exc_info=True)
        flash(f'Error generating price list: {str(e)}', 'error')
        return redirect(url_for('pricing.price_list'))

@pricing_bp.route('/delete-price', methods=['POST'])
@require_auth
def delete_price():
    user_email = session.get('user_email')
    item_name = request.form.get('item')
    
    if not item_name:
        flash('Item name is required', 'error')
        return redirect(url_for('pricing.price_list'))
    
    # Get current price list
    price_list = get_price_list(user_email)
    
    if item_name in price_list:
        del price_list[item_name]
        # Save updated price list
        save_result = save_price_list(user_email, price_list)
        
        if save_result:
            flash('Price deleted successfully', 'success')
        else:
            flash('Error saving updated price list', 'error')
    else:
        flash('Item not found', 'error')
    
    return redirect(url_for('pricing.price_list'))

@pricing_bp.route('/add-price', methods=['POST'])
@require_auth
def add_price():
    user_email = session.get('user_email')
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
    
    # Get current price list
    price_list = get_price_list(user_email)
    price_list[item] = {"unit": unit, "price": price}
    
    # Save updated price list
    save_result = save_price_list(user_email, price_list)
    
    if save_result:
        flash('Price added successfully', 'success')
    else:
        flash('Error saving updated price list', 'error')
        
    return redirect(url_for('pricing.price_list'))

@pricing_bp.route('/update-price', methods=['POST'])
@require_auth
def update_price():
    user_email = session.get('user_email')
    item = request.form.get('item')
    unit = request.form.get('unit')
    price = request.form.get('price')
    old_item = request.form.get('displayItemName')
    
    if not all([item, unit, price]):
        flash('All fields are required', 'error')
        return redirect(url_for('pricing.price_list'))
    
    try:
        price = float(price)
    except ValueError:
        flash('Price must be a number', 'error')
        return redirect(url_for('pricing.price_list'))
    
    # Get current price list
    price_list = get_price_list(user_email)
    
    # If item name was changed, remove the old item
    if old_item and old_item != item and old_item in price_list:
        del price_list[old_item]
    
    # Add or update the item
    price_list[item] = {"unit": unit, "price": price}
    
    # Save updated price list
    save_result = save_price_list(user_email, price_list)
    
    if save_result:
        flash('Price updated successfully', 'success')
    else:
        flash('Error saving updated price list', 'error')
        
    return redirect(url_for('pricing.price_list'))
