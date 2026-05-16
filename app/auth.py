import os
from authlib.integrations.flask_client import OAuth
from flask import Blueprint, redirect, url_for, session, current_app
from .models import db, User

oauth = OAuth()
auth_bp = Blueprint('auth', __name__)


def _register_oidc():
    oauth.register(
        name='oidc',
        client_id=os.getenv('OIDC_CLIENT_ID'),
        client_secret=os.getenv('OIDC_CLIENT_SECRET'),
        server_metadata_url=os.getenv('OIDC_SERVER_METADATA_URL'),
        client_kwargs={'scope': 'openid profile email'},
    )

@auth_bp.record_once
def on_load(state):
    _register_oidc()

@auth_bp.route('/login')
def login():
    redirect_uri = url_for('auth.auth_callback', _external=True)
    return oauth.oidc.authorize_redirect(redirect_uri)

@auth_bp.route('/auth/callback')
def auth_callback():
    token = oauth.oidc.authorize_access_token()
    userinfo = token.get('userinfo') or oauth.oidc.userinfo()
    sub = userinfo['sub']
    user = User.query.filter_by(sub=sub).first()
    if not user:
        user = User(sub=sub)
        db.session.add(user)
    user.name = userinfo.get('name')
    user.email = userinfo.get('email')
    user.avatar_url = userinfo.get('picture')
    db.session.commit()
    session['user_id'] = user.id
    return redirect(url_for('main.index'))

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))
