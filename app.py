import os
from datetime import datetime
import json
import csv
from io import StringIO
from collections import Counter

from flask import Flask, render_template, url_for, request, redirect, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')
db = SQLAlchemy(app)

class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return '<Task %r>' % self.id


class ProjectTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    priority = db.Column(db.String(10), default='Medium', nullable=False)
    category = db.Column(db.String(50), default='General', nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    image_filename = db.Column(db.String(255), nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return '<ProjectTask %r>' % self.id


def ensure_project_task_schema():
    with db.engine.connect() as connection:
        result = connection.execute("PRAGMA table_info(project_task)")
        existing_columns = {row[1] for row in result.fetchall()}

        if 'category' not in existing_columns:
            connection.execute("ALTER TABLE project_task ADD COLUMN category VARCHAR(50) DEFAULT 'General'")
        if 'due_date' not in existing_columns:
            connection.execute("ALTER TABLE project_task ADD COLUMN due_date DATE")
        if 'image_filename' not in existing_columns:
            connection.execute("ALTER TABLE project_task ADD COLUMN image_filename VARCHAR(255)")


with app.app_context():
    db.create_all()
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    ensure_project_task_schema()


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/assignment/', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        task_content = request.form['content'].strip()
        
        # Validation: check if content is empty
        if not task_content or len(task_content) > 200:
            return render_template('assignment/index.html', 
                                 tasks=Todo.query.order_by(Todo.date_created).all(),
                                 error='Task must be between 1 and 200 characters')
        
        new_task = Todo(content=task_content)
        try:
            db.session.add(new_task)
            db.session.commit()
            return redirect('/assignment/')
        except:
            return 'There was an issue adding your task'

    else:
        # Get sort and search parameters
        sort_by = request.args.get('sort', 'date_asc')
        search_query = request.args.get('search', '').strip()
        
        # Query all tasks
        if search_query:
            tasks = Todo.query.filter(Todo.content.ilike(f'%{search_query}%')).all()
        else:
            tasks = Todo.query.all()
        
        # Sort tasks
        if sort_by == 'date_desc':
            tasks = sorted(tasks, key=lambda x: x.date_created, reverse=True)
        else:  # date_asc (default)
            tasks = sorted(tasks, key=lambda x: x.date_created)
        
        return render_template('assignment/index.html', 
                             tasks=tasks, 
                             sort_by=sort_by,
                             search_query=search_query)


@app.route('/assignment/delete/<int:id>')
def delete(id):
    task_to_delete = Todo.query.get_or_404(id)

    try:
        db.session.delete(task_to_delete)
        db.session.commit()
        return redirect('/assignment/')
    except:
        return 'There was a problem deleting that task'

@app.route('/assignment/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    task = Todo.query.get_or_404(id)

    if request.method == 'POST':
        task.content = request.form['content']

        try:
            db.session.commit()
            return redirect('/assignment/')
        except:
            return 'There was an issue updating your task'

    else:
        return render_template('assignment/update.html', task=task)


# PROJECT ROUTES
@app.route('/project/', methods=['POST', 'GET'])
def project_index():
    if request.method == 'POST':
        task_content = request.form['content'].strip()
        priority = request.form.get('priority', 'Medium')
        category = request.form.get('category', 'General')
        due_date_raw = request.form.get('due_date', '').strip()
        
        # Validation: check if content is empty
        if not task_content or len(task_content) > 200:
            tasks = ProjectTask.query.order_by(ProjectTask.date_created).all()
            today_date = datetime.utcnow().date()
            return render_template('project/index.html', 
                                 tasks=tasks,
                                 today_date=today_date,
                                 error='Task must be between 1 and 200 characters')

        due_date_value = None
        if due_date_raw:
            try:
                due_date_value = datetime.strptime(due_date_raw, '%Y-%m-%d').date()
            except ValueError:
                tasks = ProjectTask.query.order_by(ProjectTask.date_created).all()
                today_date = datetime.utcnow().date()
                return render_template('project/index.html',
                                     tasks=tasks,
                                     today_date=today_date,
                                     error='Due date must be a valid date in YYYY-MM-DD format')

        image_file = request.files.get('image')
        image_filename = None
        if image_file and image_file.filename:
            image_filename = f"{int(datetime.utcnow().timestamp())}_{secure_filename(image_file.filename)}"
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image_file.save(image_path)
        
        new_task = ProjectTask(
            content=task_content,
            priority=priority,
            category=category,
            due_date=due_date_value,
            image_filename=image_filename
        )
        try:
            db.session.add(new_task)
            db.session.commit()
            return redirect('/project/')
        except:
            return 'There was an issue adding your task'

    else:
        # Get sort and search parameters
        sort_by = request.args.get('sort', 'date_asc')
        priority_filter = request.args.get('priority', 'All')
        category_filter = request.args.get('category', 'All')
        search_query = request.args.get('search', '').strip()
        
        # Query tasks
        query = ProjectTask.query
        if priority_filter != 'All':
            query = query.filter_by(priority=priority_filter)
        if category_filter != 'All':
            query = query.filter_by(category=category_filter)
        
        if search_query:
            tasks = query.filter(ProjectTask.content.ilike(f'%{search_query}%')).all()
        else:
            tasks = query.all()
        
        # Sort tasks
        if sort_by == 'date_desc':
            tasks = sorted(tasks, key=lambda x: x.date_created, reverse=True)
        elif sort_by == 'priority':
            priority_order = {'High': 1, 'Medium': 2, 'Low': 3}
            tasks = sorted(tasks, key=lambda x: priority_order.get(x.priority, 4))
        else:  # date_asc (default)
            tasks = sorted(tasks, key=lambda x: x.date_created)

        today_date = datetime.utcnow().date()
        
        return render_template('project/index.html', 
                             tasks=tasks, 
                             sort_by=sort_by,
                             priority_filter=priority_filter,
                             category_filter=category_filter,
                             search_query=search_query,
                             today_date=today_date)


@app.route('/project/export/csv')
def project_export_csv():
    tasks = ProjectTask.query.order_by(ProjectTask.date_created.desc()).all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Task', 'Priority', 'Category', 'Due Date', 'Image File', 'Created At'])

    for task in tasks:
        writer.writerow([
            task.id,
            task.content,
            task.priority,
            task.category,
            task.due_date.isoformat() if task.due_date else '',
            task.image_filename or '',
            task.date_created.isoformat()
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = 'attachment; filename=project_tasks.csv'
    return response


@app.route('/project/delete/<int:id>')
def project_delete(id):
    task_to_delete = ProjectTask.query.get_or_404(id)

    try:
        db.session.delete(task_to_delete)
        db.session.commit()
        return redirect('/project/')
    except:
        return 'There was a problem deleting that task'


@app.route('/project/update/<int:id>', methods=['GET', 'POST'])
def project_update(id):
    task = ProjectTask.query.get_or_404(id)

    if request.method == 'POST':
        task.content = request.form['content'].strip()
        task.priority = request.form.get('priority', 'Medium')
        task.category = request.form.get('category', 'General')
        due_date_raw = request.form.get('due_date', '').strip()
        if due_date_raw:
            try:
                task.due_date = datetime.strptime(due_date_raw, '%Y-%m-%d').date()
            except ValueError:
                return render_template('project/update.html', task=task, error='Due date must be a valid date in YYYY-MM-DD format')
        else:
            task.due_date = None

        image_file = request.files.get('image')
        if image_file and image_file.filename:
            image_filename = f"{int(datetime.utcnow().timestamp())}_{secure_filename(image_file.filename)}"
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image_file.save(image_path)
            task.image_filename = image_filename

        try:
            db.session.commit()
            return redirect('/project/')
        except:
            return 'There was an issue updating your task'

    else:
        return render_template('project/update.html', task=task)


@app.route('/project/dashboard/')
def project_dashboard():
    tasks = ProjectTask.query.all()
    total_tasks = len(tasks)

    overdue_tasks = 0
    no_due_date_tasks = 0
    today = datetime.utcnow().date()
    for task in tasks:
        if task.due_date is None:
            no_due_date_tasks += 1
        elif task.due_date < today:
            overdue_tasks += 1

    priority_counter = Counter(task.priority for task in tasks)
    category_counter = Counter(task.category for task in tasks)

    priority_labels = ['High', 'Medium', 'Low']
    priority_values = [priority_counter.get(label, 0) for label in priority_labels]

    category_labels = sorted(category_counter.keys()) if category_counter else []
    category_values = [category_counter[label] for label in category_labels]

    return render_template(
        'project/dashboard.html',
        total_tasks=total_tasks,
        overdue_tasks=overdue_tasks,
        no_due_date_tasks=no_due_date_tasks,
        priority_labels=json.dumps(priority_labels),
        priority_values=json.dumps(priority_values),
        category_labels=json.dumps(category_labels),
        category_values=json.dumps(category_values)
    )


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
