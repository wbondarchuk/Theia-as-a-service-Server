# main.py

from flask import Blueprint, render_template, request, session, current_app, flash, url_for, redirect
from flask_login import current_user, login_required

from .docker_manager import create_container, force_remove_container, get_URL, start_container
from . import db
from .models import User, Container
from .config import DOCKER_WAIT_TIME_IN_SECONDS

main = Blueprint('main', __name__)


@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    username = current_user.name
    if request.method == 'POST':
        data = request.form.getlist('chkbox')

        if 'rename_btn' in request.form:
            rnm = User.query.filter_by(email=session.get("email")).first().cont
            for c in rnm:
                cont_name = request.form.get(f'cont_name{c.id}')
                container = Container.query.filter_by(id=c.id).first()
                old_name = container.container_name
                container.container_name = cont_name
                db.session.commit()
                current_app.logger.info(f'Renamed container id={container.id}: old name "{old_name}", new name "{container.container_name}"')

        elif 'create_btn' in request.form:
            try:
                container_id = create_container()
            except Exception as e:
                flash(str(e), 'danger')

        elif 'delete_btn' in request.form:
            for id in data:
                force_remove_container(id)

        elif 'share_btn' in request.form:
            for id in data:
                URL = get_URL(id, username)
                flash('Be careful! Everyone will be able to connect to the container using your link!')
                flash(f'Your link: {URL}')

        elif 'run_btn' in request.form:
            for id in data:
                start_container(id)
                URL = get_URL(id, username)
                return render_template('loader.html'), {"Refresh": f"{DOCKER_WAIT_TIME_IN_SECONDS}; url={URL}"}

    info = []
    try:
        info = User.query.filter_by(email=session.get("email")).first().cont
    except Exception as e:
        current_app.logger.error(e)


    return render_template('profile.html', name=username, list=info)
