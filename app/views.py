from app import app, lm
from flask import render_template, flash, redirect, session, url_for, request, abort, make_response, g
from flask_login import login_user, logout_user, current_user, login_required
from .forms import LoginForm, RegisterForm, ChangePasswordForm, \
        ProfileForm, PostForm, CommentForm, ReplyForm, SearchForm
from .models import User, Permission, Role, Post, Comment
from . import db
from datetime import datetime
from .decorators import admin_required, permission_required


@app.errorhandler(404)
def internal_error(error):
    return render_template('404.html', title='404'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html', title='500'), 500

@app.route('/')
@app.route('/index')
def index():
    page = request.args.get('page', 1, type=int)
    pagination = Post.query.order_by(Post.timestamp.desc()).paginate(
        page, per_page=app.config['POSTS_PER_PAGE'],
        error_out=False
    )
    posts = pagination.items
    return render_template('index.html',title = '首页',posts=posts,
                           pagination=pagination, Permission=Permission)

@app.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('index'))
        flash('账号或密码无效。')
    return render_template('login.html',
                           title = '登录',
                           form =form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('你已经登出账号。')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,
                    nickname=form.nickname.data,
                    password=form.password.data)
        db.session.add(user)
        flash('你可以登录了。')
        return redirect(url_for('login'))
    return render_template('register.html',
                           form=form,
                           title='注册')

@app.route('/changepassword', methods=['GET','POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.old_password.data):
            current_user.password = form.password.data
            db.session.add(current_user)
            flash('你的密码已经更改。')
            return redirect(url_for('index'))
        else:
            flash('无效的密码。')
    return render_template('change_password.html',
                           form=form,
                           title='更改密码')

@app.route('/user/<nickname>')
# @login_required
def user(nickname):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('未发现用户：' + nickname)
        return redirect(url_for('index'))
    posts = user.posts.order_by(Post.timestamp.desc()).all()
    return render_template('user.html',
                           user=user,
                           posts=posts,
                           Permission=Permission,
                           title='个人资料')

# 用户最后一次访问时间,全文搜索
@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now()
        db.session.add(current_user)
        db.session.commit()
    g.search_form = SearchForm()

# 编辑用户资料
@app.route('/editprofile', methods=['GET','POST'])
@login_required
def editprofile():
    form = ProfileForm()
    if form.validate_on_submit():
        current_user.nickname = form.nickname.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user)
        flash('更改资料成功。')
        return redirect(url_for('editprofile'))
    else:
        form.nickname.data = current_user.nickname
        form.about_me.data = current_user.about_me
    return render_template('editprofile.html', form=form, title='编辑资料')

# 博客文章
@app.route('/write', methods=['GET', 'POST'])
def write():
    form = PostForm()
    if current_user.operation(Permission.WRITE_ARTICLES) and \
            form.validate_on_submit():
        post = Post(body=form.body.data,
                    title=form.title.data,
                    author = current_user._get_current_object())

        db.session.add(post)
        flash('发布成功！')
        return redirect(url_for('write'))
    return render_template('write.html', form=form,post=form.body.data,
                           title='写文章')

@app.route('/post/<int:id>', methods=['GET','POST'])
def post(id):
    post = Post.query.get_or_404(id)
    post.view_num += 1
    db.session.add(post)
    # 评论
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(body=form.body.data, post=post,
                          author=current_user._get_current_object())
        db.session.add(comment)
        flash('你的评论已经发表成功。')
        return redirect(url_for('post', id=post.id, page=-1))
    page = request.args.get('page', 1, type=int)
    if page == -1:
        page = (post.comments.count() - 1) / \
            app.config['COMMENTS_PER_PAGE'] + 1
    pagination = post.comments.order_by(Comment.timestamp.asc()).paginate(
        page, per_page=app.config['COMMENTS_PER_PAGE'],
        error_out=False
    )
    comments = pagination.items
    return render_template('post.html', posts=[post],
                           title=post.title,id=post.id,post=post,
                           form=form, comments=comments,
                           pagination=pagination)

# 交互回复评论
@app.route('/reply/<int:id>', methods=['GET','POST'])
@login_required
def reply(id):
    comment = Comment.query.get_or_404(id)
    post = Post.query.get_or_404(comment.post_id)
    page = request.args.get('page', 1, type=int)
    form = ReplyForm()
    if form.validate_on_submit():
        reply_comment = Comment(body=form.body.data,
                            post=post,comment_type='reply',
                            reply_to=comment.author.nickname,
                            author=current_user._get_current_object())
        db.session.add(reply_comment)
        flash('你的回复已经发表。')
        return redirect(url_for('post', id=comment.post_id, page=page))
    return render_template('reply.html', form=form, nickname=comment.author.nickname, title='回复')


# 管理评论
# 恢复评论，即是将Comment模型的disabled的布尔值设为Flase
@app.route('/recover/<int:id>')
@login_required
def recover(id):
    comment = Comment.query.get_or_404(id)
    post_id = comment.post_id
    comment.disabled = False
    db.session.add(comment)
    return redirect(url_for('post',id=post_id))
# 删除评论
@app.route('/delate/<int:id>')
@login_required
def delate(id):
    comment = Comment.query.get_or_404(id)
    post_id = comment.post_id
    comment.disabled = True
    db.session.add(comment)
    return redirect(url_for('post',id=post_id))

# 编辑文章
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and \
        not current_user.operation(Permission.ADMINISTER):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.body = form.body.data
        db.session.add(post)
        flash('更新成功。')
        return redirect(url_for('post', id=post.id))
    form.title.data = post.title
    form.body.data = post.body
    return render_template('editpost.html', form=form, title='编辑文章')

# 关注路由
@app.route('/follow/<nickname>')
@login_required
@permission_required(Permission.FOLLOW)
def follow(nickname):
    user = User.query.filter_by(nickname=nickname).first()
    if user is None:
        flash('无效的用户。')
        return redirect(url_for('index'))
    if current_user.is_following(user):
        flash('你已经关注了此用户。')
        return redirect(url_for('user', nickname=nickname))
    current_user.follow(user)
    flash('你已关注 %s。' % nickname)
    return redirect(url_for('user', nickname=nickname))

# 取消关注
@app.route('/unfollow/<nickname>')
@login_required
@permission_required(Permission.FOLLOW)
def unfollow(nickname):
    user = User.query.filter_by(nickname=nickname).first()
    if user is None:
        flash('无效的用户。')
        return redirect(url_for('.index'))
    if not current_user.is_following(user):
        flash('你已经取消了此用户的关注。')
        return redirect(url_for('.user', nickname=nickname))
    current_user.unfollow(user)
    flash('你已取消关注 %s 。' % nickname)
    return redirect(url_for('user', nickname=nickname))


@app.route('/follows/<nickname>')
def follows(nickname):
    user = User.query.filter_by(nickname=nickname).first()
    if user is None:
        flash('无效的用户。')
        return redirect(url_for('index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followers.paginate(
        page, per_page=app.config['FOLLOWERS_PER_PAGE'],
        error_out=False
    )
    pagination2 = user.followed.paginate(
        page, per_page=app.config['FOLLOWERS_PER_PAGE'],
        error_out=False
    )
    show_followed = False
    if current_user.is_authenticated:
        show_followed = bool(request.cookies.get('show_followed',''))
        posts = current_user.followed_posts
    else:
        posts = Post.query
    if show_followed:
        follows = [{'user': i.follower, 'timestamp': i.timestamp}
                   for i in pagination.items]
    else:
        follows = [{'user': i.followed, 'timestamp': i.timestamp}
                   for i in pagination2.items]

    return render_template('follow.html', user=user,
                           title='关注',
                           show_followed=show_followed,
                           pagination=pagination,
                           Permission=Permission,
                           posts=posts,
                           follows=follows)

@app.route('/followers/<nickname>')
def show_follower(nickname):
    resp = make_response(redirect(url_for('follows',nickname=nickname)))
    resp.set_cookie('show_followed','1',max_age=30*24*60*60)
    return resp
@app.route('/followed/<nickname>')
def show_followed(nickname):
    resp = make_response(redirect(url_for('follows',nickname=nickname)))
    resp.set_cookie('show_followed','',max_age=30*24*60*60)
    return resp

# 全文搜索
@app.route('/search', methods=['GET','POST'])
def search():
    if not g.search_form.validate_on_submit():
        return redirect(url_for('index'))
    return redirect(url_for('search_results', query=g.search_form.search.data))
# 搜索结果
@app.route('/search_results/<query>')
def search_results(query):
    results = Post.query.whooshee_search(query).all()
    return render_template('search_results.html',query=query,
                           title='搜索结果',posts=results)

