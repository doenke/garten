import os
from urllib.parse import urlparse
import requests
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



def _download_avatar(user, avatar_url):
    if not avatar_url:
        return
    avatar_folder = current_app.config['AVATAR_FOLDER']
    os.makedirs(avatar_folder, exist_ok=True)
    ext = os.path.splitext(urlparse(avatar_url).path)[1] or '.jpg'
    filename = f"{user.sub}{ext}"
    target = os.path.join(avatar_folder, filename)
    try:
        res = requests.get(avatar_url, timeout=10)
        res.raise_for_status()
        with open(target, 'wb') as f:
            f.write(res.content)
        user.avatar_filename = filename
    except requests.RequestException:
        current_app.logger.warning('Could not download avatar for %s', user.sub)

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
    _download_avatar(user, user.avatar_url)
    db.session.commit()
    session['user_id'] = user.id
    return redirect(url_for('main.index'))

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))
