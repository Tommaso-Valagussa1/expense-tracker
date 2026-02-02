from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import extract, func
from itsdangerous import URLSafeTimedSerializer
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Environment-based configuration
if os.environ.get("PYTHONANYWHERE_SITE") == 'true':
    # Production on PythonAnywhere
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
else:
    # Local development
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expense_tracker.db'
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER", 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT", 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_USERNAME")

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    expense_categories = db.relationship('ExpenseCategory', backref='user', lazy=True, cascade='all, delete-orphan')
    income_categories = db.relationship('IncomeCategory', backref='user', lazy=True, cascade='all, delete-orphan')
    savings_categories = db.relationship('SavingsCategory', backref='user', lazy=True, cascade='all, delete-orphan')
    expenses = db.relationship('Expense', backref='user', lazy=True, cascade='all, delete-orphan')
    incomes = db.relationship('Income', backref='user', lazy=True, cascade='all, delete-orphan')
    savings = db.relationship('Savings', backref='user', lazy=True, cascade='all, delete-orphan')
    budgets = db.relationship('Budget', backref='user', lazy=True, cascade='all, delete-orphan')
    ignored_notifications = db.relationship('IgnoredNotification', backref='user', lazy=True, cascade='all, delete-orphan')

class ExpenseCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('expense_category.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subcategories = db.relationship('ExpenseCategory', backref=db.backref('parent', remote_side=[id]), lazy=True)
    expenses = db.relationship('Expense', backref='category', lazy=True, cascade='all, delete-orphan')
    budgets = db.relationship('Budget', backref='category', lazy=True, cascade='all, delete-orphan')

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_category.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
class IgnoredNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notification_type = db.Column(db.String(50), nullable=False)  # e.g., 'missing_budget'
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    ignored_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class IncomeCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    incomes = db.relationship('Income', backref='category', lazy=True, cascade='all, delete-orphan')

class SavingsCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    savings = db.relationship('Savings', backref='category', lazy=True, cascade='all, delete-orphan')

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_category.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    category_id = db.Column(db.Integer, db.ForeignKey('income_category.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Savings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    category_id = db.Column(db.Integer, db.ForeignKey('savings_category.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_now():
    return {'now': datetime.now}

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        
        flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    expense_categories = ExpenseCategory.query.filter_by(user_id=current_user.id, parent_id=None).all()
    income_categories = IncomeCategory.query.filter_by(user_id=current_user.id).all()
    savings_categories = SavingsCategory.query.filter_by(user_id=current_user.id).all()
    
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    expenses = Expense.query.filter_by(user_id=current_user.id).filter(
        extract('month', Expense.date) == current_month,
        extract('year', Expense.date) == current_year
    ).all()
    
    incomes = Income.query.filter_by(user_id=current_user.id).filter(
        extract('month', Income.date) == current_month,
        extract('year', Income.date) == current_year
    ).all()
    
    savings = Savings.query.filter_by(user_id=current_user.id).filter(
        extract('month', Savings.date) == current_month,
        extract('year', Savings.date) == current_year
    ).all()
    
    # Check for missing budgets
    categories_without_budget = []
    for cat in expense_categories:
        budget = Budget.query.filter_by(
            user_id=current_user.id,
            category_id=cat.id,
            month=current_month,
            year=current_year
        ).first()
        if not budget:
            categories_without_budget.append(cat.name)
    
    # Check if notification is ignored for today
    show_budget_warning = False
    if categories_without_budget:
        ignored = IgnoredNotification.query.filter_by(
            user_id=current_user.id,
            notification_type='missing_budget',
            month=current_month,
            year=current_year
        ).first()
        
        if ignored:
            # Check if it's been ignored today
            if ignored.ignored_date.date() < datetime.now().date():
                show_budget_warning = True
        else:
            show_budget_warning = True
    
    # Calculate total budget for current month
    budgets = Budget.query.filter_by(
        user_id=current_user.id,
        month=current_month,
        year=current_year
    ).all()
    total_budget = sum(b.amount for b in budgets)
    
    return render_template('dashboard.html', 
                         expense_categories=expense_categories,
                         income_categories=income_categories,
                         savings_categories=savings_categories,
                         expenses=expenses,
                         incomes=incomes,
                         savings=savings,
                         categories_without_budget=categories_without_budget,
                         show_budget_warning=show_budget_warning,
                         total_budget=total_budget)

@app.route('/setup')
@login_required
def setup():
    expense_categories = ExpenseCategory.query.filter_by(user_id=current_user.id, parent_id=None).all()
    income_categories = IncomeCategory.query.filter_by(user_id=current_user.id).all()
    savings_categories = SavingsCategory.query.filter_by(user_id=current_user.id).all()
    
    return render_template('setup.html',
                         expense_categories=expense_categories,
                         income_categories=income_categories,
                         savings_categories=savings_categories)

@app.route('/add_expense_category', methods=['POST'])
@login_required
def add_expense_category():
    name = request.form.get('name')
    parent_id = request.form.get('parent_id')
    
    category = ExpenseCategory(
        name=name,
        parent_id=parent_id if parent_id else None,
        user_id=current_user.id
    )
    db.session.add(category)
    db.session.commit()
    
    flash('Expense category added successfully')
    return redirect(url_for('setup'))

@app.route('/set_budget', methods=['POST'])
@login_required
def set_budget():
    category_id = request.form.get('category_id')
    amount = float(request.form.get('budget'))
    month = int(request.form.get('month'))
    year = int(request.form.get('year'))
    
    category = ExpenseCategory.query.get(category_id)
    if category and category.user_id == current_user.id:
        # Check if budget already exists for this month/year
        existing_budget = Budget.query.filter_by(
            user_id=current_user.id,
            category_id=category_id,
            month=month,
            year=year
        ).first()
        
        if existing_budget:
            existing_budget.amount = amount
            flash('Budget updated successfully')
        else:
            budget = Budget(
                amount=amount,
                month=month,
                year=year,
                category_id=category_id,
                user_id=current_user.id
            )
            db.session.add(budget)
            flash('Budget set successfully')
        
        db.session.commit()
    else:
        flash('Category not found')
    
    return redirect(url_for('setup'))

@app.route('/delete_expense_category/<int:category_id>', methods=['POST'])
@login_required
def delete_expense_category(category_id):
    category = ExpenseCategory.query.get(category_id)
    if category and category.user_id == current_user.id:
        # Check if category has expenses
        if category.expenses:
            flash(f'Cannot delete "{category.name}" - it has {len(category.expenses)} transactions. Delete those first.')
        # Check if category has subcategories
        elif category.subcategories:
            flash(f'Cannot delete "{category.name}" - it has subcategories. Delete those first.')
        else:
            db.session.delete(category)
            db.session.commit()
            flash('Category deleted successfully')
    else:
        flash('Category not found')
    
    return redirect(url_for('setup'))

@app.route('/ignore_budget_notification', methods=['POST'])
@login_required
def ignore_budget_notification():
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    # Check if already ignored
    existing = IgnoredNotification.query.filter_by(
        user_id=current_user.id,
        notification_type='missing_budget',
        month=current_month,
        year=current_year
    ).first()
    
    if existing:
        existing.ignored_date = datetime.now()
    else:
        ignored = IgnoredNotification(
            user_id=current_user.id,
            notification_type='missing_budget',
            month=current_month,
            year=current_year,
            ignored_date=datetime.now()
        )
        db.session.add(ignored)
    
    db.session.commit()
    flash('Budget notification hidden until tomorrow')
    return redirect(url_for('dashboard'))

@app.route('/delete_income_category/<int:category_id>', methods=['POST'])
@login_required
def delete_income_category(category_id):
    category = IncomeCategory.query.get(category_id)
    if category and category.user_id == current_user.id:
        # Check if category has income entries
        if category.incomes:
            flash(f'Cannot delete "{category.name}" - it has {len(category.incomes)} transactions. Delete those first.')
        else:
            db.session.delete(category)
            db.session.commit()
            flash('Category deleted successfully')
    else:
        flash('Category not found')
    
    return redirect(url_for('setup'))

@app.route('/delete_savings_category/<int:category_id>', methods=['POST'])
@login_required
def delete_savings_category(category_id):
    category = SavingsCategory.query.get(category_id)
    if category and category.user_id == current_user.id:
        # Check if category has savings entries
        if category.savings:
            flash(f'Cannot delete "{category.name}" - it has {len(category.savings)} transactions. Delete those first.')
        else:
            db.session.delete(category)
            db.session.commit()
            flash('Category deleted successfully')
    else:
        flash('Category not found')
    
    return redirect(url_for('setup'))

@app.route('/delete_expense/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.get(expense_id)
    if expense and expense.user_id == current_user.id:
        db.session.delete(expense)
        db.session.commit()
        flash('Expense deleted successfully')
    else:
        flash('Expense not found')
    
    return redirect(url_for('dashboard'))

@app.route('/delete_income/<int:income_id>', methods=['POST'])
@login_required
def delete_income(income_id):
    income = Income.query.get(income_id)
    if income and income.user_id == current_user.id:
        db.session.delete(income)
        db.session.commit()
        flash('Income deleted successfully')
    else:
        flash('Income not found')
    
    return redirect(url_for('dashboard'))

@app.route('/delete_savings/<int:savings_id>', methods=['POST'])
@login_required
def delete_savings(savings_id):
    saving = Savings.query.get(savings_id)
    if saving and saving.user_id == current_user.id:
        db.session.delete(saving)
        db.session.commit()
        flash('Savings deleted successfully')
    else:
        flash('Savings not found')
    
    return redirect(url_for('dashboard'))

@app.route('/edit_expense/<int:expense_id>', methods=['POST'])
@login_required
def edit_expense(expense_id):
    expense = Expense.query.get(expense_id)
    if expense and expense.user_id == current_user.id:
        expense.amount = float(request.form.get('amount'))
        expense.category_id = request.form.get('category_id')
        expense.description = request.form.get('description')
        expense.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
        db.session.commit()
        flash('Expense updated successfully')
    else:
        flash('Expense not found')
    
    return redirect(url_for('dashboard'))

@app.route('/edit_income/<int:income_id>', methods=['POST'])
@login_required
def edit_income(income_id):
    income = Income.query.get(income_id)
    if income and income.user_id == current_user.id:
        income.amount = float(request.form.get('amount'))
        income.category_id = request.form.get('category_id')
        income.description = request.form.get('description')
        income.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
        db.session.commit()
        flash('Income updated successfully')
    else:
        flash('Income not found')
    
    return redirect(url_for('dashboard'))

@app.route('/edit_savings/<int:savings_id>', methods=['POST'])
@login_required
def edit_savings(savings_id):
    saving = Savings.query.get(savings_id)
    if saving and saving.user_id == current_user.id:
        saving.amount = float(request.form.get('amount'))
        saving.category_id = request.form.get('category_id')
        saving.description = request.form.get('description')
        saving.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
        db.session.commit()
        flash('Savings updated successfully')
    else:
        flash('Savings not found')
    
    return redirect(url_for('dashboard'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            token = serializer.dumps(email, salt='password-reset-salt')
            reset_url = url_for('reset_password', token=token, _external=True)
            
            try:
                msg = Message('Password Reset Request',
                            recipients=[email])
                msg.body = f'''Hi {user.username},

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you didn't request this, please ignore this email.
'''
                mail.send(msg)
                flash('Password reset instructions sent to your email')
            except Exception as e:
                flash('Error sending email. Please try again later.')
                print(f"Email error: {e}")
        else:
            flash('If an account exists with that email, reset instructions have been sent.')
        
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash('The reset link is invalid or has expired.')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user:
            user.password_hash = generate_password_hash(password)
            db.session.commit()
            flash('Your password has been reset successfully!')
            return redirect(url_for('login'))
    
    return render_template('reset_password.html', token=token)

@app.route('/add_income_category', methods=['POST'])
@login_required
def add_income_category():
    name = request.form.get('name')
    category = IncomeCategory(name=name, user_id=current_user.id)
    db.session.add(category)
    db.session.commit()
    
    flash('Income category added successfully')
    return redirect(url_for('setup'))

@app.route('/add_savings_category', methods=['POST'])
@login_required
def add_savings_category():
    name = request.form.get('name')
    category = SavingsCategory(name=name, user_id=current_user.id)
    db.session.add(category)
    db.session.commit()
    
    flash('Savings category added successfully')
    return redirect(url_for('setup'))

@app.route('/add_expense', methods=['POST'])
@login_required
def add_expense():
    amount = float(request.form.get('amount'))
    description = request.form.get('description')
    category_id = request.form.get('category_id')
    date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
    
    expense = Expense(
        amount=amount,
        description=description,
        category_id=category_id,
        user_id=current_user.id,
        date=date
    )
    db.session.add(expense)
    db.session.commit()
    
    flash('Expense added successfully')
    return redirect(url_for('dashboard'))

@app.route('/add_income', methods=['POST'])
@login_required
def add_income():
    amount = float(request.form.get('amount'))
    description = request.form.get('description')
    category_id = request.form.get('category_id')
    date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
    
    income = Income(
        amount=amount,
        description=description,
        category_id=category_id,
        user_id=current_user.id,
        date=date
    )
    db.session.add(income)
    db.session.commit()
    
    flash('Income added successfully')
    return redirect(url_for('dashboard'))

@app.route('/add_savings', methods=['POST'])
@login_required
def add_savings():
    amount = float(request.form.get('amount'))
    description = request.form.get('description')
    category_id = request.form.get('category_id')
    date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
    
    saving = Savings(
        amount=amount,
        description=description,
        category_id=category_id,
        user_id=current_user.id,
        date=date
    )
    db.session.add(saving)
    db.session.commit()
    
    flash('Savings added successfully')
    return redirect(url_for('dashboard'))

@app.route('/analytics')
@login_required
def analytics():
    return render_template('analytics.html')

@app.route('/api/analytics_data')
@login_required
def analytics_data():
    # Get month and year from query params, default to current
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    # Expense by category
    expense_by_category = db.session.query(
        ExpenseCategory.name,
        func.sum(Expense.amount).label('total')
    ).join(Expense).filter(
        Expense.user_id == current_user.id,
        extract('month', Expense.date) == month,
        extract('year', Expense.date) == year
    ).group_by(ExpenseCategory.name).all()
    
    # Savings by category
    savings_by_category = db.session.query(
        SavingsCategory.name,
        func.sum(Savings.amount).label('total')
    ).join(Savings).filter(
        Savings.user_id == current_user.id,
        extract('month', Savings.date) == month,
        extract('year', Savings.date) == year
    ).group_by(SavingsCategory.name).all()
    
    # Budget vs Spend for parent categories
    parent_categories = ExpenseCategory.query.filter_by(
        user_id=current_user.id,
        parent_id=None
    ).all()
    
    budget_vs_spend = []
    category_details = []
    
    for cat in parent_categories:
        # Get budget for this month/year
        budget_entry = Budget.query.filter_by(
            user_id=current_user.id,
            category_id=cat.id,
            month=month,
            year=year
        ).first()
        
        budget_amount = budget_entry.amount if budget_entry else 0
        
        # Calculate total spent (including subcategories)
        category_ids = [cat.id] + [sub.id for sub in cat.subcategories]
        total_spent = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == current_user.id,
            Expense.category_id.in_(category_ids),
            extract('month', Expense.date) == month,
            extract('year', Expense.date) == year
        ).scalar() or 0
        
        budget_vs_spend.append({
            'name': cat.name,
            'budget': float(budget_amount),
            'spent': float(total_spent)
        })
        
        # Detailed breakdown for each category
        category_details.append({
            'name': cat.name,
            'budget': float(budget_amount),
            'spent': float(total_spent)
        })
    
    # Monthly timeline (last 6 months from selected month)
    monthly_data = []
    budget_timeline = []
    
    for i in range(6):
        target_month = month - i
        target_year = year
        
        # Handle year rollover
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        
        total_expense = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == current_user.id,
            extract('month', Expense.date) == target_month,
            extract('year', Expense.date) == target_year
        ).scalar() or 0
        
        # Get total budget for this month
        total_budget = db.session.query(func.sum(Budget.amount)).filter(
            Budget.user_id == current_user.id,
            Budget.month == target_month,
            Budget.year == target_year
        ).scalar() or 0
        
        monthly_data.insert(0, {
            'month': f"{target_year}-{target_month:02d}",
            'amount': float(total_expense)
        })
        budget_timeline.insert(0, float(total_budget))
    
    return jsonify({
        'expense_by_category': [{'name': name, 'amount': float(total)} for name, total in expense_by_category],
        'savings_by_category': [{'name': name, 'amount': float(total)} for name, total in savings_by_category],
        'budget_vs_spend': budget_vs_spend,
        'category_details': category_details,
        'monthly_timeline': monthly_data,
        'budget_timeline': budget_timeline
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Use environment variable for debug mode
    debug_mode = not os.environ.get('PYTHONANYWHERE_SITE')
    app.run(debug=debug_mode, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))