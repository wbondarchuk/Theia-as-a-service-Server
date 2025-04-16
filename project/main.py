# main.py

from flask import Blueprint, render_template, request, session, current_app, flash, url_for, redirect
from flask_login import current_user, login_required

from .docker_manager import create_container, force_remove_container, get_URL, start_container
from . import db
from .models import User, Container, UserContainer
from .config import DOCKER_WAIT_TIME_IN_SECONDS

main = Blueprint('main', __name__)


@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    username = current_user.name

    if request.method == 'POST' and 'run_btn' in request.form:
        container_id = request.form.get('container_id')

        # Проверяем, есть ли связь между текущим пользователем и контейнером
        user_container = UserContainer.query.filter_by(user_id=current_user.id, container_id=container_id).first()

        if user_container:
            # Если контейнер найден, запускаем его
            start_container(container_id)
            URL = get_URL(container_id, username)
            return render_template('loader.html'), {"Refresh": f"{DOCKER_WAIT_TIME_IN_SECONDS}; url={URL}"}

    # Получаем контейнеры пользователя через таблицу UserContainer
    containers = [uc.container for uc in current_user.container_links]

    return render_template('profile.html',
                           name=username,
                           list=containers)