import os
import csv
import io
from datetime import datetime, date, timedelta
from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort, current_app, Response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.utils.decorators import mess_manager_required
from app.models import db, Student, User, BedAllocation
from app.models.mess import (
    MessProfile, Supplier, MealMenu, MealBooking, MealAttendance,
    MealFeedback, MessInventory, InventoryTransaction, MessExpense,
    MessStaffProfile, MessNotice, MessBillingRecord
)
from app.services.mess_service import MessService

mess_manager_bp = Blueprint('mess_manager', __name__)

def _get_manager_mess():
    """Retrieves the active mess profile for management"""
    return MessService.get_or_create_default_mess()

@mess_manager_bp.route('/dashboard')
@login_required
@mess_manager_required
def dashboard():
    """Mess Manager Executive Dashboard with real-time stats and Chart.js analytics"""
    mess = _get_manager_mess()
    today = date.today()
    first_day_of_month = date(today.year, today.month, 1)

    # Core Stats
    total_students = Student.query.count()
    today_menus = MealMenu.query.filter_by(mess_id=mess.id, meal_date=today).all()

    breakfast_att = sum(m.attendance_count for m in today_menus if m.meal_type == 'Breakfast')
    lunch_att = sum(m.attendance_count for m in today_menus if m.meal_type == 'Lunch')
    snacks_att = sum(m.attendance_count for m in today_menus if m.meal_type == 'Snacks')
    dinner_att = sum(m.attendance_count for m in today_menus if m.meal_type == 'Dinner')

    total_active_bookings = MealBooking.query.join(MealMenu).filter(
        MealMenu.mess_id == mess.id,
        MealMenu.meal_date == today,
        MealBooking.booking_status == 'Booked'
    ).count()

    total_inventory_items = MessInventory.query.filter_by(mess_id=mess.id).count()
    low_stock_items = MessInventory.query.filter(
        MessInventory.mess_id == mess.id,
        MessInventory.quantity <= MessInventory.minimum_stock_level
    ).count()

    # Expenses this month
    expenses_month = db.session.query(db.func.sum(MessExpense.amount)).filter(
        MessExpense.mess_id == mess.id,
        MessExpense.transaction_date >= first_day_of_month
    ).scalar() or Decimal('0.00')

    # Feedback score
    feedbacks = MealFeedback.query.join(MealMenu).filter(MealMenu.mess_id == mess.id).all()
    avg_rating = round(sum(f.rating for f in feedbacks) / len(feedbacks), 1) if feedbacks else 0.0

    # Chart 1: Daily attendance trend over past 7 days
    daily_labels = []
    daily_attendance = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        daily_labels.append(d.strftime('%a, %d %b'))
        cnt = MealAttendance.query.join(MealMenu).filter(
            MealMenu.mess_id == mess.id,
            MealMenu.meal_date == d,
            MealAttendance.attendance_status.in_(['Present', 'Walk-in'])
        ).count()
        daily_attendance.append(cnt)

    # Chart 2: Expense category breakdown
    category_expenses = db.session.query(
        MessExpense.expense_category,
        db.func.sum(MessExpense.amount)
    ).filter(
        MessExpense.mess_id == mess.id,
        MessExpense.transaction_date >= first_day_of_month
    ).group_by(MessExpense.expense_category).all()

    expense_labels = [c[0] for c in category_expenses] or ['Groceries', 'Dairy', 'Fuel', 'Maintenance']
    expense_data = [float(c[1]) for c in category_expenses] or [0, 0, 0, 0]

    # Recent activities
    recent_bookings = MealBooking.query.join(MealMenu).filter(
        MealMenu.mess_id == mess.id
    ).order_by(MealBooking.created_at.desc()).limit(5).all()

    recent_feedbacks = MealFeedback.query.join(MealMenu).filter(
        MealMenu.mess_id == mess.id
    ).order_by(MealFeedback.created_at.desc()).limit(5).all()

    recent_expenses = MessExpense.query.filter_by(mess_id=mess.id).order_by(
        MessExpense.transaction_date.desc(), MessExpense.id.desc()
    ).limit(5).all()

    return render_template('mess_manager/dashboard.html',
                           mess=mess,
                           total_students=total_students,
                           breakfast_att=breakfast_att,
                           lunch_att=lunch_att,
                           snacks_att=snacks_att,
                           dinner_att=dinner_att,
                           total_active_bookings=total_active_bookings,
                           total_inventory_items=total_inventory_items,
                           low_stock_items=low_stock_items,
                           expenses_month=expenses_month,
                           avg_rating=avg_rating,
                           daily_labels=daily_labels,
                           daily_attendance=daily_attendance,
                           expense_labels=expense_labels,
                           expense_data=expense_data,
                           recent_bookings=recent_bookings,
                           recent_feedbacks=recent_feedbacks,
                           recent_expenses=recent_expenses)


# =====================================================================
# MENU MANAGEMENT
# =====================================================================

@mess_manager_bp.route('/menu')
@login_required
@mess_manager_required
def menu_list():
    """Weekly calendar and list view for daily meals"""
    mess = _get_manager_mess()
    selected_date_str = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    try:
        current_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        current_date = date.today()

    weekly_calendar = MessService.get_weekly_menus(mess.id, current_date)
    menus = MealMenu.query.filter_by(mess_id=mess.id).order_by(
        MealMenu.meal_date.desc(), MealMenu.meal_type.asc()
    ).limit(30).all()

    return render_template('mess_manager/menu/list.html',
                           mess=mess,
                           current_date=current_date,
                           weekly_calendar=weekly_calendar,
                           menus=menus)


@mess_manager_bp.route('/menu/create', methods=['GET', 'POST'])
@login_required
@mess_manager_required
def menu_create():
    """Create and schedule a new meal slot"""
    mess = _get_manager_mess()

    if request.method == 'POST':
        meal_date_str = request.form.get('meal_date')
        meal_type = request.form.get('meal_type')
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        food_category = request.form.get('food_category', 'Vegetarian')
        meal_timing = request.form.get('meal_timing', '').strip()
        booking_deadline_str = request.form.get('booking_deadline')
        capacity = request.form.get('capacity', 250, type=int)
        is_published = bool(request.form.get('is_published'))

        try:
            meal_date = datetime.strptime(meal_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            flash('Invalid meal date format.', 'danger')
            return redirect(url_for('mess_manager.menu_create'))

        try:
            booking_deadline = datetime.strptime(booking_deadline_str, '%Y-%m-%dT%H:%M')
        except (ValueError, TypeError):
            # Default to 2 hours before standard timing
            booking_deadline = datetime.combine(meal_date, datetime.min.time()) + timedelta(hours=6)

        # Check for unique slot collision
        existing = MealMenu.query.filter_by(
            mess_id=mess.id,
            meal_date=meal_date,
            meal_type=meal_type
        ).first()

        if existing:
            flash(f'A menu for {meal_type} on {meal_date.strftime("%d %b, %Y")} already exists.', 'warning')
            return redirect(url_for('mess_manager.menu_list'))

        # Handle image upload if provided
        food_image_path = None
        if 'food_image' in request.files:
            file = request.files['food_image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                ext = os.path.splitext(filename)[1].lower()
                if ext in ['.png', '.jpg', '.jpeg', '.webp']:
                    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'food_images')
                    os.makedirs(upload_dir, exist_ok=True)
                    saved_name = f"food_{int(datetime.utcnow().timestamp())}_{filename}"
                    file.save(os.path.join(upload_dir, saved_name))
                    food_image_path = f"uploads/food_images/{saved_name}"

        menu = MealMenu(
            mess_id=mess.id,
            meal_date=meal_date,
            meal_type=meal_type,
            title=title,
            description=description,
            food_category=food_category,
            meal_timing=meal_timing or '8:00 AM - 10:00 AM',
            booking_deadline=booking_deadline,
            capacity=capacity,
            is_published=is_published,
            food_image=food_image_path,
            created_by=current_user.id
        )
        db.session.add(menu)
        db.session.commit()

        flash(f'{meal_type} menu "{title}" created successfully.', 'success')
        return redirect(url_for('mess_manager.menu_list'))

    return render_template('mess_manager/menu/form.html',
                           mess=mess,
                           menu=None,
                           today=date.today())


@mess_manager_bp.route('/menu/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@mess_manager_required
def menu_edit(id):
    """Edit meal particulars and timings"""
    menu = MealMenu.query.get_or_404(id)
    mess = _get_manager_mess()

    if request.method == 'POST':
        menu.title = request.form.get('title', '').strip()
        menu.description = request.form.get('description', '').strip()
        menu.food_category = request.form.get('food_category', menu.food_category)
        menu.meal_timing = request.form.get('meal_timing', menu.meal_timing)
        menu.capacity = request.form.get('capacity', menu.capacity, type=int)
        menu.is_published = bool(request.form.get('is_published'))

        deadline_str = request.form.get('booking_deadline')
        if deadline_str:
            try:
                menu.booking_deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass

        if 'food_image' in request.files:
            file = request.files['food_image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                ext = os.path.splitext(filename)[1].lower()
                if ext in ['.png', '.jpg', '.jpeg', '.webp']:
                    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'food_images')
                    os.makedirs(upload_dir, exist_ok=True)
                    saved_name = f"food_{int(datetime.utcnow().timestamp())}_{filename}"
                    file.save(os.path.join(upload_dir, saved_name))
                    menu.food_image = f"uploads/food_images/{saved_name}"

        menu.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Meal menu "{menu.title}" updated successfully.', 'success')
        return redirect(url_for('mess_manager.menu_list'))

    return render_template('mess_manager/menu/form.html',
                           mess=mess,
                           menu=menu,
                           today=date.today())


@mess_manager_bp.route('/menu/<int:id>/toggle-publish', methods=['POST'])
@login_required
@mess_manager_required
def menu_toggle_publish(id):
    """Publishes or hides a future meal menu"""
    menu = MealMenu.query.get_or_404(id)
    menu.is_published = not menu.is_published
    menu.updated_at = datetime.utcnow()
    db.session.commit()
    status_text = "published for booking" if menu.is_published else "hidden/unpublished"
    flash(f'{menu.meal_type} menu is now {status_text}.', 'info')
    return redirect(request.referrer or url_for('mess_manager.menu_list'))


@mess_manager_bp.route('/menu/<int:id>/delete', methods=['POST'])
@login_required
@mess_manager_required
def menu_delete(id):
    """Safely deletes an unpublished meal with zero active bookings or check-in records"""
    menu = MealMenu.query.get_or_404(id)

    # Constraint safeguard: prevent deleting if bookings or attendance already exist
    if menu.bookings.count() > 0 or menu.attendances.count() > 0:
        flash('Cannot delete meal: Active student bookings or attendance records already exist. Unpublish the meal instead.', 'danger')
        return redirect(url_for('mess_manager.menu_list'))

    db.session.delete(menu)
    db.session.commit()
    flash('Meal menu deleted successfully.', 'success')
    return redirect(url_for('mess_manager.menu_list'))


# =====================================================================
# BOOKINGS & ATTENDANCE MANAGEMENT
# =====================================================================

@mess_manager_bp.route('/bookings')
@login_required
@mess_manager_required
def bookings_list():
    """Master dining reservation register"""
    mess = _get_manager_mess()
    selected_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    status_filter = request.args.get('status', '')

    try:
        filter_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except ValueError:
        filter_date = date.today()

    query = MealBooking.query.join(MealMenu).filter(
        MealMenu.mess_id == mess.id,
        MealMenu.meal_date == filter_date
    )

    if status_filter:
        query = query.filter(MealBooking.booking_status == status_filter)

    bookings = query.order_by(MealBooking.created_at.desc()).all()
    today_menus = MealMenu.query.filter_by(mess_id=mess.id, meal_date=filter_date).all()

    return render_template('mess_manager/bookings.html',
                           mess=mess,
                           bookings=bookings,
                           selected_date=filter_date,
                           today_menus=today_menus,
                           status_filter=status_filter)


@mess_manager_bp.route('/attendance')
@login_required
@mess_manager_required
def attendance_list():
    """Master meal attendance audit log with export and search"""
    mess = _get_manager_mess()
    selected_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    slot_filter = request.args.get('slot', '')

    try:
        filter_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except ValueError:
        filter_date = date.today()

    query = MealAttendance.query.join(MealMenu).filter(
        MealMenu.mess_id == mess.id,
        MealMenu.meal_date == filter_date
    )

    if slot_filter:
        query = query.filter(MealMenu.meal_type == slot_filter)

    attendances = query.order_by(MealAttendance.check_in_time.desc()).all()

    return render_template('mess_manager/attendance.html',
                           mess=mess,
                           attendances=attendances,
                           selected_date=filter_date,
                           slot_filter=slot_filter)


# =====================================================================
# INVENTORY & SUPPLIERS
# =====================================================================

@mess_manager_bp.route('/inventory')
@login_required
@mess_manager_required
def inventory_list():
    """Pantry stock levels, category filters, and low-stock alerts"""
    mess = _get_manager_mess()
    category = request.args.get('category', '')
    status_filter = request.args.get('status', '')  # 'low_stock', 'expired'
    search_q = request.args.get('q', '').strip()

    query = MessInventory.query.filter_by(mess_id=mess.id)

    if category:
        query = query.filter_by(category=category)
    if status_filter == 'low_stock':
        query = query.filter(MessInventory.quantity <= MessInventory.minimum_stock_level)
    elif status_filter == 'expired':
        query = query.filter(MessInventory.expiry_date < date.today())
    if search_q:
        query = query.filter(MessInventory.item_name.ilike(f"%{search_q}%"))

    items = query.order_by(MessInventory.item_name.asc()).all()
    categories = [
        'Grains & Cereals', 'Vegetables', 'Dairy', 'Spices & Oils',
        'Pulses & Legumes', 'Snacks & Beverages', 'Gas & Kitchen Supplies', 'Other'
    ]

    return render_template('mess_manager/inventory/list.html',
                           mess=mess,
                           items=items,
                           categories=categories,
                           selected_category=category,
                           status_filter=status_filter,
                           search_q=search_q)


@mess_manager_bp.route('/inventory/add', methods=['GET', 'POST'])
@login_required
@mess_manager_required
def inventory_add():
    """Add a new item to the pantry inventory"""
    mess = _get_manager_mess()
    suppliers = Supplier.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        item_name = request.form.get('item_name', '').strip()
        category = request.form.get('category', 'Grains & Cereals')
        quantity = Decimal(request.form.get('quantity', '0.00'))
        unit = request.form.get('unit', 'kg').strip()
        min_stock = Decimal(request.form.get('minimum_stock_level', '10.00'))
        purchase_price = Decimal(request.form.get('purchase_price', '0.00'))
        supplier_id = request.form.get('supplier_id', type=int) or None
        expiry_date_str = request.form.get('expiry_date')

        expiry_date = None
        if expiry_date_str:
            try:
                expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        item = MessInventory(
            mess_id=mess.id,
            item_name=item_name,
            category=category,
            quantity=quantity,
            unit=unit,
            minimum_stock_level=min_stock,
            purchase_price=purchase_price,
            supplier_id=supplier_id,
            expiry_date=expiry_date
        )
        db.session.add(item)
        db.session.commit()

        # If initial quantity > 0, record initial purchase transaction
        if quantity > 0:
            tx = InventoryTransaction(
                inventory_id=item.id,
                transaction_type='Purchase',
                quantity=quantity,
                unit_price=purchase_price,
                total_price=quantity * purchase_price,
                supplier_id=supplier_id,
                remarks='Initial stock intake on registration',
                recorded_by=current_user.id
            )
            db.session.add(tx)
            db.session.commit()

        flash(f'Pantry item "{item_name}" registered successfully.', 'success')
        return redirect(url_for('mess_manager.inventory_list'))

    return render_template('mess_manager/inventory/form.html',
                           mess=mess,
                           suppliers=suppliers,
                           item=None)


@mess_manager_bp.route('/inventory/<int:id>/transaction', methods=['POST'])
@login_required
@mess_manager_required
def inventory_transaction(id):
    """Record stock purchase, consumption, adjustment, or wastage"""
    tx_type = request.form.get('transaction_type')
    quantity = Decimal(request.form.get('quantity', '0.00'))
    unit_price = Decimal(request.form.get('unit_price', '0.00'))
    supplier_id = request.form.get('supplier_id', type=int) or None
    reference = request.form.get('reference', '').strip()
    remarks = request.form.get('remarks', '').strip()

    result = MessService.record_inventory_transaction(
        inventory_id=id,
        tx_type=tx_type,
        quantity=quantity,
        unit_price=unit_price,
        supplier_id=supplier_id,
        reference=reference,
        remarks=remarks,
        user_id=current_user.id
    )

    if result['success']:
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'danger')

    return redirect(url_for('mess_manager.inventory_list'))


@mess_manager_bp.route('/suppliers', methods=['GET', 'POST'])
@login_required
@mess_manager_required
def suppliers():
    """Wholesale food and provision vendor management"""
    if request.method == 'POST':
        supplier_name = request.form.get('supplier_name', '').strip()
        contact_person = request.form.get('contact_person', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()

        if not supplier_name:
            flash('Supplier name is required.', 'danger')
        else:
            supplier = Supplier(
                supplier_name=supplier_name,
                contact_person=contact_person,
                phone_number=phone_number,
                email=email,
                address=address
            )
            db.session.add(supplier)
            db.session.commit()
            flash(f'Supplier "{supplier_name}" registered successfully.', 'success')
            return redirect(url_for('mess_manager.suppliers'))

    suppliers_list = Supplier.query.order_by(Supplier.supplier_name.asc()).all()
    return render_template('mess_manager/suppliers.html', suppliers=suppliers_list)


# =====================================================================
# EXPENSES & FINANCIALS
# =====================================================================

@mess_manager_bp.route('/expenses', methods=['GET', 'POST'])
@login_required
@mess_manager_required
def expenses():
    """Log and monitor operational kitchen expenditures"""
    mess = _get_manager_mess()

    if request.method == 'POST':
        category = request.form.get('category')
        description = request.form.get('description', '').strip()
        amount = Decimal(request.form.get('amount', '0.00'))
        receipt_ref = request.form.get('receipt_reference', '').strip()
        date_str = request.form.get('transaction_date')

        tx_date = None
        if date_str:
            try:
                tx_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        result = MessService.record_expense(
            mess_id=mess.id,
            category=category,
            description=description,
            amount=amount,
            receipt_reference=receipt_ref,
            user_id=current_user.id,
            tx_date=tx_date
        )

        if result['success']:
            flash(result['message'], 'success')
            return redirect(url_for('mess_manager.expenses'))
        else:
            flash(result['message'], 'danger')

    expenses_list = MessExpense.query.filter_by(mess_id=mess.id).order_by(
        MessExpense.transaction_date.desc(), MessExpense.id.desc()
    ).all()

    total_spent = sum(e.amount for e in expenses_list)
    categories = [
        'Vegetables & Groceries', 'Dairy & Milk', 'Gas & Fuel',
        'Kitchen Maintenance', 'Cleaning & Hygiene', 'Staff Salary / Wages',
        'Utensils & Equipment', 'Other'
    ]

    return render_template('mess_manager/expenses.html',
                           mess=mess,
                           expenses=expenses_list,
                           total_spent=total_spent,
                           categories=categories,
                           today=date.today())


# =====================================================================
# FEEDBACK, NOTICES, REPORTS & STAFF
# =====================================================================

@mess_manager_bp.route('/feedback')
@login_required
@mess_manager_required
def feedback():
    """Inspect student food quality ratings and reviews"""
    mess = _get_manager_mess()
    feedbacks = MealFeedback.query.join(MealMenu).filter(
        MealMenu.mess_id == mess.id
    ).order_by(MealFeedback.created_at.desc()).all()

    avg_score = round(sum(f.rating for f in feedbacks) / len(feedbacks), 1) if feedbacks else 0.0

    return render_template('mess_manager/feedback.html',
                           mess=mess,
                           feedbacks=feedbacks,
                           avg_score=avg_score)


@mess_manager_bp.route('/notices', methods=['GET', 'POST'])
@login_required
@mess_manager_required
def notices():
    """Publish dining hall announcements and special meal arrangements"""
    mess = _get_manager_mess()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        message = request.form.get('message', '').strip()
        notice_type = request.form.get('notice_type', 'General')
        expires_at_str = request.form.get('expires_at')

        exp_date = None
        if expires_at_str:
            try:
                exp_date = datetime.strptime(expires_at_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        notice = MessNotice(
            mess_id=mess.id,
            title=title,
            message=message,
            notice_type=notice_type,
            expires_at=exp_date,
            posted_by=current_user.id
        )
        db.session.add(notice)
        db.session.commit()
        flash('Dining announcement posted successfully.', 'success')
        return redirect(url_for('mess_manager.notices'))

    notices_list = MessNotice.query.filter(
        (MessNotice.mess_id == mess.id) | (MessNotice.mess_id == None)
    ).order_by(MessNotice.created_at.desc()).all()

    return render_template('mess_manager/notices.html', mess=mess, notices=notices_list)


@mess_manager_bp.route('/reports')
@login_required
@mess_manager_required
def reports():
    """Food wastage analytics and dining attendance reports"""
    mess = _get_manager_mess()
    report_date_str = request.args.get('date', date.today().strftime('%Y-%m-%d'))

    try:
        target_date = datetime.strptime(report_date_str, '%Y-%m-%d').date()
    except ValueError:
        target_date = date.today()

    wastage_data = MessService.get_wastage_report(mess.id, target_date)
    return render_template('mess_manager/reports.html', mess=mess, report=wastage_data)


@mess_manager_bp.route('/reports/export-attendance')
@login_required
@mess_manager_required
def export_attendance_csv():
    """Streams attendance log as CSV for audits and reporting"""
    mess = _get_manager_mess()
    attendances = MealAttendance.query.join(MealMenu).join(Student).filter(
        MealMenu.mess_id == mess.id
    ).order_by(MealAttendance.check_in_time.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Attendance ID', 'Date', 'Meal Slot', 'Student Name', 'Enrollment No', 'Roll No', 'Check-in Time', 'Method', 'Status', 'Remarks'])

    for a in attendances:
        writer.writerow([
            a.id,
            a.meal_menu.meal_date.strftime('%Y-%m-%d'),
            a.meal_menu.meal_type,
            a.student.full_name,
            a.student.enrollment_no,
            a.student.roll_no or 'N/A',
            a.check_in_time.strftime('%I:%M:%S %p'),
            a.verification_method,
            a.attendance_status,
            a.remarks or ''
        ])

    output.seek(0)
    return Response(output, mimetype='text/csv', headers={
        'Content-Disposition': f'attachment; filename=Mess_Attendance_Export_{date.today().strftime("%Y%m%d")}.csv'
    })


@mess_manager_bp.route('/staff')
@login_required
@mess_manager_required
def staff_list():
    """Dining hall attendants and counter staff overview"""
    mess = _get_manager_mess()
    staff_members = MessStaffProfile.query.filter_by(mess_id=mess.id).all()
    return render_template('mess_manager/staff.html', mess=mess, staff=staff_members)
