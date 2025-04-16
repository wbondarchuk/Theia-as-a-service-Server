from flask import Blueprint, render_template, request, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from .models import User, Role, Container, db, ContainerRole, UserContainer
from .docker_manager import create_container as create, force_remove_container, get_URL, start_container

admin = Blueprint('admin', __name__)

@admin.route('/admin/users')
@login_required
def user_management():
    if current_user.role != Role.ADMIN:
        current_app.logger.info(f'Access denied!')
        return redirect(url_for("main.profile"))

    users = User.query.all()
    return render_template('admin.html',
                         users=users,
                         active_tab='users')

@admin.route('/admin/create_user', methods=['GET', 'POST'])
@login_required
def create_user():
    if current_user.role != Role.ADMIN:
        current_app.logger.info(f'Access denied!')
        return redirect(url_for("main.profile"))

    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')
        role = request.form.get('role')

        if User.query.filter_by(email=email).first():
            current_app.logger.info("User with this email already exists.")
            return redirect(url_for("admin.create_user"))

        new_user = User(email=email, name=name, password=generate_password_hash(password), role=Role(role))
        db.session.add(new_user)
        db.session.commit()
        current_app.logger.info(f"User {email} created successfully!")
        return redirect(url_for("admin.user_management"))

    return render_template('create_user.html')

@admin.route('/admin/users/change_role/<int:user_id>', methods=['POST'])
@login_required
def change_role(user_id):
    if current_user.role != Role.ADMIN:
        current_app.logger.info(f'Access denied!')
        return redirect(url_for("main.profile"))

    user = User.query.get(user_id)
    if user:
        new_role = request.form.get("role")
        if new_role in Role.__members__.values():
            user.role = Role(new_role)
            db.session.commit()
            current_app.logger.info(f"Role updated for {user.email}")
        else:
            current_app.logger.info("Invalid role selected")

    return redirect(url_for("admin.user_management"))

@admin.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != Role.ADMIN:
        current_app.logger.info(f'Access denied!')
        return redirect(url_for("main.profile"))

    user = User.query.get(user_id)

    if not user:
        current_app.logger.info("User not found!")
        return redirect(url_for("admin.user_management"))

    if user.role == Role.ADMIN:
        admin_count = User.query.filter_by(role=Role.ADMIN).count()
        if admin_count <= 1:
            current_app.logger.info("Cannot delete the last administrator!")
            return redirect(url_for("admin.user_management"))

    db.session.delete(user)
    db.session.commit()
    current_app.logger.info(f'AUser {user.email} deleted')
    return redirect(url_for("admin.user_management"))

@admin.route('/admin/containers')
@login_required
def container_management():
    if current_user.role != Role.ADMIN:
        current_app.logger.info(f'Access denied!')
        return redirect(url_for("main.profile"))

    containers = Container.query.all()
    return render_template('admin.html',
                         containers=containers,
                         active_tab='containers')


@admin.route('/admin/containers/create', methods=['POST'])
@login_required
def create_container():
    if current_user.role != Role.ADMIN:
        current_app.logger.info(f'Access denied!')
        return redirect(url_for("main.profile"))

    try:
        # Создаем контейнер без привязки к пользователю
        container_id = create()
        current_app.logger.info(f'Container created successfully!')
    except Exception as e:
        current_app.logger.info(str(e), 'danger')

    return redirect(url_for('admin.container_management'))


@admin.route('/admin/containers/manage_users/<container_id>', methods=['GET', 'POST'])
@login_required
def manage_container_users(container_id):
    if current_user.role != Role.ADMIN:
        current_app.logger.info(f'Access denied!')
        return redirect(url_for("main.profile"))

    container = Container.query.get_or_404(container_id)

    if request.method == 'POST':
        selected_user_ids = request.form.getlist('user_ids')
        # Удалим старые связи
        container.user_links.clear()

        for user_id_str in selected_user_ids:
            user_id = int(user_id_str)
            role = request.form.get(f'role_{user_id}', ContainerRole.READER)
            user = User.query.get(user_id)
            if user and user.role == Role.USER:
                link = UserContainer(user=user, container=container, container_role=role)
                container.user_links.append(link)

        db.session.commit()
        current_app.logger.info("Users and roles updated successfully!")
        return redirect(url_for('admin.container_management'))

    # GET — загружаем всех пользователей и текущие роли
    all_users = User.query.filter_by(role=Role.USER).order_by(User.email).all()
    container_user_roles = {
        link.user_id: link.container_role for link in container.user_links
    }

    return render_template('manage_users.html',
                           container=container,
                           users=all_users,
                           container_user_roles=container_user_roles)

@admin.route('/admin/containers/delete/<container_id>', methods=['POST'])
@login_required
def delete_container(container_id):
    if current_user.role != Role.ADMIN:
        current_app.logger.info(f'Access denied!')
        return redirect(url_for("main.profile"))

    force_remove_container(container_id)
    current_app.logger.info("Container deleted successfully!")
    return redirect(url_for('admin.container_management'))