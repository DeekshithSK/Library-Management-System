from flask import Flask, render_template, request, redirect, url_for, session
import csv
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'your-very-secret-key-12345'  # Change this for production!

# CSV file paths
BOOKS_CSV = 'books.csv'
MEMBERS_CSV = 'members.csv'
TRANSACTIONS_CSV = 'transactions.csv'

# Add these routes
@app.before_request
def require_login():
    allowed_routes = ['login', 'static']
    if request.endpoint not in allowed_routes and not session.get('logged_in'):
        return redirect(url_for('login'))

# Modified login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == 'admin12345':
            session['logged_in'] = True
            return redirect(url_for('home'))
        return render_template('login.html', error="Invalid password")
    return render_template('login.html')

# New logout route
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

def read_csv(filename):
    try:
        with open(filename, 'r') as file:
            return list(csv.reader(file))
    except FileNotFoundError:
        return []

def write_csv(filename, data):
    with open(filename, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(data)

# Initialize CSV files with headers if they don't exist
for file, headers in [
    (BOOKS_CSV, ['id', 'title', 'author', 'isbn', 'quantity', 'category']),
    (MEMBERS_CSV, ['id', 'name', 'email']),
    (TRANSACTIONS_CSV, ['id', 'book_id', 'member_id', 'issue_date', 'return_date', 'fine'])
]:
    try:
        with open(file, 'r') as f:
            pass
    except FileNotFoundError:
        with open(file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
    if fmt:
        return date.strftime(fmt)
    else:
        return date.strftime('%Y-%m-%d')

def calculate_fine(issue_date, return_date):
    days_overdue = (return_date - issue_date).days - 30
    if days_overdue <= 0:
        return 0
    weeks_overdue = (days_overdue + 6) // 7  # Round up weeks
    return weeks_overdue * 5  # $5 per week

# Routes
@app.route('/')
def home():
    return redirect('/books')

@app.route('/books')
def books():
    raw_books = read_csv(BOOKS_CSV)[1:]  # Skip header
    processed_books = []
    for book in raw_books:
        if len(book) < 6:
            book += [''] * (6 - len(book))
        processed_books.append(book)
    return render_template('books.html', books=processed_books)

@app.route('/add_book', methods=['POST'])
def add_book():
    books = read_csv(BOOKS_CSV)
    header = books[0] if books else ['id', 'title', 'author', 'isbn', 'quantity', 'category']
    books_data = books[1:] if len(books) > 1 else []
    
    submitted_isbn = request.form['isbn'].strip()
    submitted_title = request.form['title'].strip()
    submitted_author = request.form['author'].strip()
    submitted_category = request.form['category'].strip()

    existing_book = None
    for book in books_data:
        if book[3].strip() == submitted_isbn:
            existing_book = book
            break

    if existing_book:
        if (existing_book[1] != submitted_title or 
            existing_book[2] != submitted_author or
            existing_book[5] != submitted_category):
            return "Error: ISBN exists but details don't match!"
        
        existing_book[4] = str(int(existing_book[4]) + 1)
    else:
        new_id = str(len(books))
        new_book = [
            new_id,
            submitted_title,
            submitted_author,
            submitted_isbn,
            '1',
            submitted_category
        ]
        books_data.append(new_book)

    write_csv(BOOKS_CSV, [header] + books_data)
    return redirect('/books')

@app.route('/delete_book/<book_id>')
def delete_book(book_id):
    books = read_csv(BOOKS_CSV)
    books = [books[0]] + [b for b in books[1:] if b[0] != book_id]
    write_csv(BOOKS_CSV, books)
    return redirect('/books')

@app.route('/members')
def members():
    members = read_csv(MEMBERS_CSV)[1:]  # Skip header
    return render_template('members.html', members=members)

@app.route('/add_member', methods=['POST'])
def add_member():
    members = read_csv(MEMBERS_CSV)
    new_id = str(len(members))
    new_member = [
        new_id,
        request.form['name'],
        request.form['email']
    ]
    members.append(new_member)
    write_csv(MEMBERS_CSV, members)
    return redirect('/members')

@app.route('/delete_member/<member_id>')
def delete_member(member_id):
    members = read_csv(MEMBERS_CSV)
    members = [members[0]] + [m for m in members[1:] if m[0] != member_id]
    write_csv(MEMBERS_CSV, members)
    return redirect('/members')

@app.route('/transactions')
def transactions():
    transactions_data = read_csv(TRANSACTIONS_CSV)[1:]
    books = read_csv(BOOKS_CSV)[1:]
    members = read_csv(MEMBERS_CSV)[1:]
    
    # Filter available books (quantity > 0)
    available_books = [b for b in books if int(b[4]) > 0]
    
    enriched_transactions = []
    for t in transactions_data:
        book = next((b for b in books if b[0] == t[1]), None)
        member = next((m for m in members if m[0] == t[2]), None)
        issue_date = datetime.strptime(t[3], '%Y-%m-%d')
        due_date = issue_date + timedelta(days=30)
        return_date = datetime.strptime(t[4], '%Y-%m-%d') if t[4] else None
        fine = float(t[5]) if len(t) > 5 and t[5] else 0
        
        enriched_transactions.append({
            'id': t[0],
            'book_name': book[1] if book else 'Unknown',
            'member_name': member[1] if member else 'Unknown',
            'issue_date': issue_date,
            'due_date': due_date,
            'return_date': return_date,
            'fine': fine
        })
    
    return render_template('transactions.html',
                         books=available_books,
                         members=members,
                         transactions=enriched_transactions,
                         datetime=datetime)  # Add this line

@app.route('/issue_book', methods=['POST'])
def issue_book():
    book_id = request.form['book_id']
    member_id = request.form['member_id']
    issue_date_str = request.form['issue_date']
    
    try:
        issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d')
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD"
    
    # Update book quantity
    books = read_csv(BOOKS_CSV)
    books_data = books[1:]
    
    for book in books_data:
        if book[0] == book_id:
            if int(book[4]) <= 0:
                return "Book not available!"
            book[4] = str(int(book[4]) - 1)
            break
    
    write_csv(BOOKS_CSV, [books[0]] + books_data)
    
    # Create new transaction
    transactions = read_csv(TRANSACTIONS_CSV)
    new_id = str(len(transactions))
    new_transaction = [
        new_id,
        book_id,
        member_id,
        issue_date_str,
        '',  # Return date
        '0'  # Initial fine
    ]
    transactions.append(new_transaction)
    write_csv(TRANSACTIONS_CSV, transactions)
    
    return redirect('/transactions')

@app.route('/return_book/<transaction_id>')
def return_book(transaction_id):
    transactions = read_csv(TRANSACTIONS_CSV)
    transactions_data = transactions[1:]
    
    for t in transactions_data:
        if t[0] == transaction_id and not t[4]:
            return_date = datetime.now()
            issue_date = datetime.strptime(t[3], '%Y-%m-%d')
            fine = calculate_fine(issue_date, return_date)
            
            t[4] = return_date.strftime('%Y-%m-%d')
            t[5] = str(fine)
            
            # Update book quantity
            books = read_csv(BOOKS_CSV)
            books_data = books[1:]
            
            for book in books_data:
                if book[0] == t[1]:
                    book[4] = str(int(book[4]) + 1)
                    break
            
            write_csv(BOOKS_CSV, [books[0]] + books_data)
            break
    
    write_csv(TRANSACTIONS_CSV, [transactions[0]] + transactions_data)
    return redirect('/transactions')

@app.route('/reports')
def reports():
    books = read_csv(BOOKS_CSV)[1:]
    transactions = read_csv(TRANSACTIONS_CSV)[1:]
    
    total_fines = sum(float(t[5]) for t in transactions if len(t) > 5 and t[5])
    books_issued = len([t for t in transactions if not t[4]])
    
    processed_books = []
    for book in books:
        try:
            quantity = int(book[4]) if len(book) > 4 else 0
        except (ValueError, IndexError):
            quantity = 0
        processed_books.append({
            'id': book[0],
            'title': book[1],
            'author': book[2],
            'isbn': book[3],
            'quantity': quantity,
            'category': book[5] if len(book) > 5 else 'Uncategorized'
        })
    
    return render_template('reports.html', 
                         books=processed_books,
                         total_fines=total_fines,
                         books_issued=books_issued)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        if 'password' in request.form:
            if request.form['password'] == 'admin12121':
                session['admin_authenticated'] = True
                return redirect(url_for('admin'))
            else:
                session.pop('admin_authenticated', None)
                return render_template('admin.html', error="Wrong admin password")
        else:
            if not session.get('admin_authenticated'):
                return redirect(url_for('admin'))
            
            days = int(request.form['days'])
            fine = max(0, days - 30)
            weeks_overdue = (fine + 6) // 7
            total_fine = weeks_overdue * 5
            return render_template('admin.html', 
                                 calculated=True,
                                 days=days,
                                 fine=total_fine)

    if not session.get('admin_authenticated'):
        return render_template('admin.html')
    
    return render_template('admin.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_authenticated', None)
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True, port=5009)