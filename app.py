# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user
)
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FOOD_BLOG_SECRET', 'taste-the-world')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///food_blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    summary = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(350), nullable=True)
    category = db.Column(db.String(60), nullable=True)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    author = db.relationship('User', backref=db.backref('posts', lazy=True))
    comments = db.relationship('Comment', backref='post', cascade='all, delete-orphan', lazy='dynamic')

    def hero_image(self):
        return self.image_url or "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1200&q=60"


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    author = db.relationship('User', backref=db.backref('comments', lazy=True))


def seed_demo_posts():
    if Post.query.count() == 0:
        demo_user = User.query.filter_by(username='chef').first()
        if not demo_user:
            demo_user = User(username='chef')
            demo_user.set_password('tasteatlas')
            db.session.add(demo_user)
            db.session.commit()
        demo_posts = [
            Post(
                title="Neapolitan Pizza Nights",
                summary="Wood-fired pizza with blistered crust, bright tomatoes, and creamy mozzarella.",
                content="""Those charred spots on a Neapolitan pie are flavor-packed caramelization. Layer San Marzano tomatoes, buffalo mozzarella, and basil, then bake in the hottest oven you can manage. Finish with excellent olive oil and flaky salt.""",
                image_url="https://images.unsplash.com/photo-1508739773434-c26b3d09e071?auto=format&fit=crop&w=1200&q=60",
                category="Italian",
                author=demo_user
            ),
            Post(
                title="Bangkok Market Bowl",
                summary="A rainbow curry bowl with crunchy veg, coconut broth, and jasmine rice.",
                content="""Toast your curry paste in coconut cream, add vegetables with staggered cook times, and finish with herbs, lime, and crushed peanuts. Serve over fluffy jasmine rice for balance.""",
                image_url="https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1200&q=60",
                category="Thai",
                author=demo_user
            ),
            Post(
                title="Sunrise Acai Smoothie",
                summary="Thick smoothie bowl topped with tropical fruit, cacao nibs, and chia.",
                content="""Blend frozen acai, bananas, and mango with just enough coconut water. Top with sliced fruit, granola, and seeds for crunch. A drizzle of honey ties it together.""",
                image_url="https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=1200&q=60",
                category="Breakfast",
                author=demo_user
            )
        ]
        db.session.add_all(demo_posts)
        db.session.commit()
        second_user = User.query.filter_by(username='taster').first()
        if not second_user:
            second_user = User(username='taster')
            second_user.set_password('tasteatlas')
            db.session.add(second_user)
            db.session.commit()
        sample_comments = [
            Comment(body="Tried this last weekend—turned out perfect!", post=demo_posts[0], author=second_user),
            Comment(body="Adding kaffir lime leaves really brightens the broth.", post=demo_posts[1], author=demo_user)
        ]
        db.session.add_all(sample_comments)
        db.session.commit()


@app.route('/')
def index():
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    base_query = Post.query.order_by(Post.date_posted.desc())
    if category:
        base_query = base_query.filter(Post.category.ilike(category))
    if query:
        like = f"%{query}%"
        posts = base_query.filter(or_(Post.title.ilike(like), Post.summary.ilike(like), Post.content.ilike(like))).all()
    else:
        posts = base_query.all()
    categories = db.session.query(Post.category).filter(Post.category.isnot(None)).distinct().all()
    return render_template('index.html', posts=posts, query=query, category=category, categories=[c[0] for c in categories])


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash('Log in to share a comment.', 'warning')
            return redirect(url_for('login', next=url_for('post_detail', post_id=post.id)))
        body = request.form.get('body', '').strip()
        if not body:
            flash('Comment cannot be empty.', 'danger')
            return redirect(url_for('post_detail', post_id=post.id))
        comment = Comment(body=body, post=post, author=current_user)
        db.session.add(comment)
        db.session.commit()
        flash('Comment added.', 'success')
        return redirect(url_for('post_detail', post_id=post.id))
    comments = post.comments.order_by(Comment.created_at.desc()).all()
    return render_template('post.html', post=post, comments=comments)


@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_post():
    if request.method == 'POST':
        title = request.form['title']
        summary = request.form['summary']
        content = request.form['content']
        image_url = request.form.get('image_url')
        category = request.form.get('category')
        new_post = Post(
            title=title,
            summary=summary,
            content=content,
            image_url=image_url,
            category=category,
            author=current_user
        )
        db.session.add(new_post)
        db.session.commit()
        flash('New recipe story published!', 'success')
        return redirect(url_for('index'))
    return render_template('add_post.html')


@app.route('/edit/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        flash('You can only edit your own stories.', 'danger')
        return redirect(url_for('post_detail', post_id=post.id))
    if request.method == 'POST':
        post.title = request.form['title']
        post.summary = request.form['summary']
        post.content = request.form['content']
        post.image_url = request.form.get('image_url')
        post.category = request.form.get('category')
        db.session.commit()
        flash('Post updated with fresh flavors.', 'info')
        return redirect(url_for('post_detail', post_id=post.id))
    return render_template('edit_post.html', post=post)


@app.route('/delete/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        flash('You can only delete your own stories.', 'danger')
        return redirect(url_for('post_detail', post_id=post.id))
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted.', 'warning')
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash('You are already signed in.', 'info')
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password']
        confirm = request.form['confirm_password']
        if not username or not password:
            flash('Username and password are required.', 'danger')
            return redirect(url_for('register'))
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Username already exists. Try another.', 'warning')
            return redirect(url_for('register'))
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Welcome back!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Signed out successfully.', 'info')
    return redirect(url_for('index'))


@app.context_processor
def inject_year():
    return {'current_year': datetime.utcnow().year}


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_demo_posts()
    app.run(debug=True, port=5005)
