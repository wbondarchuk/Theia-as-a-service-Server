from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from .models import User, Role
from . import db

admin = Blueprint('admin', __name__)

@admin.route('/admin/users')
@login_required
def user_management():
    if current_user.role != Role.ADMIN:
        flash("Access denied!")
        return redirect(url_for("main.profile"))

    users = User.query.all()
    return render_template('admin.html', users=users)

@admin.route('/admin/create_user', methods=['GET', 'POST'])
@login_required
def create_user():
    if current_user.role != Role.ADMIN:
        flash("Access denied!")
        return redirect(url_for("main.profile"))

    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')
        role = request.form.get('role')

        if User.query.filter_by(email=email).first():
            flash("User with this email already exists.")
            return redirect(url_for("admin.create_user"))

        new_user = User(email=email, name=name, password=generate_password_hash(password), role=Role(role))
        db.session.add(new_user)
        db.session.commit()
        flash(f"User {email} created successfully!")
        return redirect(url_for("admin.user_management"))

    return render_template('create_user.html')

@admin.route('/admin/users/change_role/<int:user_id>', methods=['POST'])
@login_required
def change_role(user_id):
    if current_user.role != Role.ADMIN:
        flash("Access denied!")
        return redirect(url_for("main.profile"))

    user = User.query.get(user_id)
    if user:
        new_role = request.form.get("role")
        if new_role in Role.__members__.values():
            user.role = Role(new_role)
            db.session.commit()
            flash(f"Role updated for {user.email}")
        else:
            flash("Invalid role selected")

    return redirect(url_for("admin.user_management"))

@admin.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != Role.ADMIN:
        flash("Access denied!")
        return redirect(url_for("main.profile"))

    user = User.query.get(user_id)

    if not user:
        flash("User not found!")
        return redirect(url_for("admin.user_management"))

    if user.role == Role.ADMIN:
        admin_count = User.query.filter_by(role=Role.ADMIN).count()
        if admin_count <= 1:
            flash("Cannot delete the last administrator!")
            return redirect(url_for("admin.user_management"))

    db.session.delete(user)
    db.session.commit()
    flash(f"User {user.email} deleted")
    return redirect(url_for("admin.user_management"))
