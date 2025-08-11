import os
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

app = Flask(__name__, static_folder="static", template_folder="templates")

# Ensure SQLAlchemy friendly scheme and sslmode=require for Supabase
def _normalize_db_url(raw_url: str) -> str:
    if not raw_url:
        raise RuntimeError("DATABASE_URL not set")
    url = raw_url.strip()
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    elif url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    parsed = urlparse(url)
    qs = dict(parse_qsl(parsed.query))
    if "sslmode" not in {k.lower(): v for k, v in qs.items()}:
        qs["sslmode"] = "require"
    new_query = urlencode(qs)
    url = urlunparse(parsed._replace(query=new_query))
    return url

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
db_url = os.getenv("DATABASE_URL", "").strip()
if not db_url and os.getenv("FLASK_ENV") == "development":
    db_url = "sqlite:///dev.sqlite3"

app.config["SQLALCHEMY_DATABASE_URI"] = _normalize_db_url(db_url) if db_url else "sqlite:///dev.sqlite3"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class Item(db.Model):
    __tablename__ = "items"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="todo")
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<Item {self.id} {self.title!r}>"

with app.app_context():
    db.create_all()

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    query = Item.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Item.title.ilike(like), Item.description.ilike(like)))
    if status:
        query = query.filter(Item.status == status)
    items = query.order_by(Item.created_at.desc()).all()
    counts = {
        "all": Item.query.count(),
        "todo": Item.query.filter_by(status="todo").count(),
        "in-progress": Item.query.filter_by(status="in-progress").count(),
        "done": Item.query.filter_by(status="done").count(),
    }
    return render_template("index.html", items=items, q=q, status=status, counts=counts)

@app.route("/items/new", methods=["GET", "POST"])
def create_item():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        status = request.form.get("status", "todo").strip()
        if not title:
            flash("Title is required", "danger")
            return render_template("item_form.html", item=None)
        if status not in {"todo", "in-progress", "done"}:
            status = "todo"
        item = Item(title=title, description=description, status=status)
        db.session.add(item)
        db.session.commit()
        flash("Item created", "success")
        return redirect(url_for("index"))
    return render_template("item_form.html", item=None)

@app.route("/items/<int:item_id>")
def show_item(item_id):
    item = Item.query.get_or_404(item_id)
    return render_template("show.html", item=item)

@app.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        status = request.form.get("status", "todo").strip()
        if not title:
            flash("Title is required", "danger")
            return render_template("item_form.html", item=item)
        if status not in {"todo", "in-progress", "done"}:
            status = "todo"
        item.title = title
        item.description = description
        item.status = status
        db.session.commit()
        flash("Item updated", "success")
        return redirect(url_for("index"))
    return render_template("item_form.html", item=item)

@app.route("/items/<int:item_id>/delete", methods=["POST"])
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Item deleted", "success")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=bool(os.getenv("FLASK_DEBUG")))
