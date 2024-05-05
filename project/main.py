# main.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from .models import Decision, Evidence, Response
from . import db
from sqlalchemy import not_

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
import base64

main = Blueprint('main', __name__)

@main.before_request
def clear_session():
    if request.endpoint != 'main.answer_decision':
        session['responses'] = []

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
@login_required
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

def has_user_answered_decision(user_id, decision_id):
    # Query the Response table to check if the user has answered the decision
    response = Response.query.filter_by(user_id=user_id, decision_id=decision_id).first()
    
    # If a response exists, return True (user has answered), otherwise return False
    return response is not None

@main.route('/feed')
def feed():
    decisions = Decision.query.all()
    return render_template('feed.html', decisions=decisions, has_user_answered_decision=has_user_answered_decision)

@main.route('/answer-decision/<int:decision_id>', methods=["GET", "POST"])
@login_required
def answer_decision(decision_id):

    if has_user_answered_decision(current_user.id, decision_id):
        return "You have already answered this questionaire!"

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
        responses_index = len(session['responses'])

        if (responses_index == num_evidences or 
            session['responses'][-1] == '10' or 
            session['responses'][-1] == '-10'):
            # All evidences responseed, process the responses
            # You can store the responses in a database or perform any other desired action
            for i in range(len(session['responses'])):
                response = Response(
                    value=float(session['responses'][i]),
                    user_id=current_user.id,
                    evidence_id=decision.evidences[i].id,
                    decision_id=decision.id)    
                db.session.add(response)
            decision.num_responses += 1
            db.session.commit()

            session['responses'] = []

            return redirect(url_for('main.graph',  decision_id=decision.id))
        

    current_evidence = decision.evidences[responses_index]
    return render_template('answer_decision.html', decision=decision, evidence=current_evidence, responses_index=responses_index, num_evidences=num_evidences, prev_value=prev_value)    

def make_drift_diffusion_model(evidences_texts, my_scores, other_scores, decision):
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
    time_intervals = evidences_texts
    scores_over_time = [current_score] + my_scores

    # Plot the graph
    plt.figure(figsize=(12, 8))  # Increase figure size
    plt.plot(scores_over_time, marker='o')
    for res_list in other_scores.values():
        plt.plot(res_list, marker='o', color='gray')

    plt.xticks(rotation=45, ha='right')

    plt.xticks(range(len(time_intervals) + 1), ['Start'] + time_intervals)
    plt.xlabel('Evidence')
    plt.ylabel('Decision Score')
    plt.title('Decision Score Evolution Over Time')

    # Set y-axis limits and center at 0
    plt.ylim(-10, 10)
    plt.yticks(range(-10, 11, 1))  # Set discrete intervals of 1
    plt.axhline(0, color='black', linestyle='--')

    # Add labels at the top and bottom right of x-axis
    plt.text(len(time_intervals), -10.5, decision.choice_1, ha='right')
    plt.text(len(time_intervals), 10.5, decision.choice_2, ha='right')

    plt.grid(True)

    # Save the figure with higher resolution
    plt.tight_layout()  # Adjust layout to make all elements fit
    plt.savefig('score_evolution.png', dpi=300)  # Save with higher resolution
    # plt.show()

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

    evidences_texts = []
    my_scores = []
    other_scores = None

    for evidence in evidences:
        evidences_texts.append(evidence.text)

        response = Response.query.filter_by(user_id=current_user.id, evidence_id=evidence.id).first()
        if response:
            my_scores.append(response.value)
        
        other_responses = Response.query.filter(not_(Response.user_id == current_user.id), Response.evidence_id == evidence.id).all()
        if other_scores is None:
            other_scores = {res.user_id : [] for res in other_responses }
        for res in other_responses:
            other_scores[res.user_id].append(res.value)
       

    image_data = make_drift_diffusion_model(evidences_texts, my_scores, other_scores, decision)

    return render_template('graph.html', image_data=image_data, decision=decision)