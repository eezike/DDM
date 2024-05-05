# main.py

from flask import Blueprint, render_template, request, redirect, url_for, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os

from .models import Problem, Question
from . import db

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/profile')
@login_required
def profile():
    problems = current_user.problems.all()
    return render_template('profile.html', name=current_user.name, problems=problems)

@main.route('/delete-problem/<int:problem_id>')
@login_required
def delete_problem(problem_id):
    problem = Problem.query.get_or_404(problem_id)
    if problem.user != current_user:
        return 403
    
    db.session.delete(problem)
    db.session.commit()
    return redirect(url_for('main.profile'))

@main.route('/create')
@login_required
def create():
    return render_template('create.html')

@main.route('/create', methods=["POST"])
@login_required
def create_post():
    title = request.form['title']
    questions = request.form.getlist('questions[]')
    emoji = request.form['emoji']
    
    problem = Problem(title=title, emoji=emoji, user_id=current_user.id)
    db.session.add(problem)
    db.session.flush()

    for question_text in questions:
        question = Question(text=question_text, problem_id=problem.id)
        db.session.add(question)

    db.session.commit()
    return redirect(url_for('main.profile'))


@main.route('/feed')
@login_required
def feed():
    problems = Problem.query.all()
    return render_template('feed.html', problems=problems)

@main.route('/answer-problem/<int:problem_id>', methods=["GET", "POST"])
@login_required
def answer_problem(problem_id):
    problem = Problem.query.get_or_404(problem_id)
    if request.method == 'POST':

        answer = request.form.get('answer')
        if 'answers' not in session:
            session['answers'] = []

        session['answers'].append(answer)
        session.modified = True


        if (len(session['answers']) == problem.questions.count() or 
            session['answers'][-1] == '10' or 
            session['answers'][-1] == '-10'):
            # All questions answered, process the answers
            # You can store the answers in a database or perform any other desired action
            return redirect(url_for('main.graph'))
        else:
            current_question = problem.questions[len(session['answers'])]
            return render_template('answer_problem.html', problem=problem, question=current_question)
    else:
        session['answers'] = []
        current_question = problem.questions[0]
        return render_template('answer_problem.html', problem=problem, question=current_question)    

@main.route('/graph', methods=["GET", "POST"])
@login_required
def graph():
    return render_template('graph.html')