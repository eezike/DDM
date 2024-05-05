# main.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from .models import Decision, Evidence, Response
from . import db

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
import base64

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/about')
def about():
    return render_template('about.html')

@main.route('/profile')
@login_required
def profile():
    decisions = current_user.decisions.all()
    return render_template('profile.html', name=current_user.name, decisions=decisions)

@main.route('/delete_decision/<int:decision_id>', methods=['POST'])
def delete_decision(decision_id):
    decision = Decision.query.get_or_404(decision_id)

    # Delete responses associated with the decision's evidences
    for evidence in decision.evidences:
        Response.query.filter_by(evidence_id=evidence.id).delete()

    # Delete evidences associated with the decision
    Evidence.query.filter_by(decision_id=decision.id).delete()

    # Delete the decision itself
    db.session.delete(decision)
    db.session.commit()

    flash('Decision and associated evidences and responses have been deleted.', 'success')
    return redirect(url_for('main.profile'))

@main.route('/create')
@login_required
def create():
    return render_template('create.html')

@main.route('/create', methods=["POST"])
@login_required
def create_post():
    main_problem = request.form['main_problem']
    evidences = request.form.getlist('evidences[]')
    emoji = request.form['emoji']
    choice_1 = request.form['choice_1']
    choice_2 = request.form['choice_2']
    
    decision = Decision(main_problem=main_problem, emoji=emoji, user_id=current_user.id, choice_1=choice_1, choice_2=choice_2)
    db.session.add(decision)
    db.session.flush()

    for evidence_text in evidences:
        evidence = Evidence(text=evidence_text, decision_id=decision.id)
        db.session.add(evidence)

    db.session.commit()
    return redirect(url_for('main.profile'))


@main.route('/feed')
@login_required
def feed():
    decisions = Decision.query.all()
    return render_template('feed.html', decisions=decisions)

@main.route('/answer-decision/<int:decision_id>', methods=["GET", "POST"])
@login_required
def answer_decision(decision_id):

    decision = Decision.query.get_or_404(decision_id)

    if 'responses' not in session:
        session['responses'] = []
    
    responses_index = len(session['responses'])
    num_evidences = decision.evidences.count()

    prev_value = 0 if session['responses'] == [] else session['responses'][-1]

    if request.method == 'POST':

        response = request.form.get('response')
        session['responses'].append(response)
        session.modified = True

        print(session['responses'])
        prev_value = session['responses'][-1]

        if (responses_index == num_evidences or 
            session['responses'][-1] == '10' or 
            session['responses'][-1] == '-10'):
            # All evidences responseed, process the responses
            # You can store the responses in a database or perform any other desired action
            for i in range(num_evidences):
                response = Response(value=float(session['responses'][i]), user_id=current_user.id, evidence_id=decision.evidences[i].id)    
                db.session.add(response)
            db.session.commit()

            session['responses'] = []

            decision.num_responses += 1

            return redirect(url_for('main.graph',  decision_id=decision.id))
        

    current_evidence = decision.evidences[responses_index]
    return render_template('answer_decision.html', decision=decision, evidence=current_evidence, responses_index=responses_index, num_evidences=num_evidences, prev_value=prev_value)    

def make_drift_diffusion_model(evidence_to_score):
    # Define the evidence and scores
    # evidence_to_score = {
    #     "My crush will be there.": 5,
    #     "I have homework due tomorrow.": -2,
    #     "It is a $20 entry fee.": -3,
    #     "They will have my favorite food.": 4,
    #     "They will play my favorite music!": 10
    # }

    # Initialize variables
    current_score = 0
    time_intervals = list(evidence_to_score.keys())
    scores_over_time = [current_score]

    # Calculate scores over time
    for evidence_name in time_intervals:
        current_score = evidence_to_score[evidence_name]
        scores_over_time.append(current_score)

    # Plot the graph
    plt.figure(figsize=(10, 6))
    plt.plot(scores_over_time, marker='o')
    plt.xticks(rotation=45, ha='right')
    plt.xticks(range(len(time_intervals) + 1), ['Start'] + time_intervals)
    plt.xlabel('Evidence')
    plt.ylabel('Descision Score')
    plt.title('Decision Score Evolution Over Time')

    # Set y-axis limits and center at 0
    plt.ylim(-10, 10)
    plt.yticks(range(-10, 11, 1))  # Set discrete intervals of 1
    plt.axhline(0, color='black', linestyle='--')

    plt.grid(True)
    #plt.show()

    # Convert the plot to a base64-encoded image
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
    plt.close()

    return image_data


@main.route('/graph/<int:decision_id>')
@login_required
def graph(decision_id):
    decision = Decision.query.get_or_404(decision_id)
    evidences = decision.evidences.all()
    evidence_to_score = dict()

    for evidence in evidences:
        response = Response.query.filter_by(user_id=current_user.id, evidence_id=evidence.id).first()
        if response:
            evidence_to_score[evidence.text] = response.value
        else:
           break

    if not evidence_to_score:
        return "No responses found for the specified decision and user."

    image_data = make_drift_diffusion_model(evidence_to_score)

    return render_template('graph.html', image_data=image_data, decision=decision)