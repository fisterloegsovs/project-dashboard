import logging
import os
import secrets
from datetime import datetime, timezone
from flask import Flask, jsonify, request, redirect, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import requests as http_requests

log = logging.getLogger(__name__)

app = Flask(__name__)

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
CORS(app, origins=[FRONTEND_URL], supports_credentials=True)

basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'dashboard.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# GitHub OAuth configuration — set these env vars before running
app.config["GITHUB_CLIENT_ID"] = os.environ.get("GITHUB_CLIENT_ID", "")
app.config["GITHUB_CLIENT_SECRET"] = os.environ.get("GITHUB_CLIENT_SECRET", "")
app.config["FRONTEND_URL"] = FRONTEND_URL

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API = "https://api.github.com"

db = SQLAlchemy(app)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    color = db.Column(db.String(7), default="#6366f1")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    tasks = db.relationship("Task", backref="project", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "created_at": self.created_at.isoformat(),
            "task_count": len(self.tasks),
            "completed_count": sum(1 for t in self.tasks if t.status == "completed"),
        }


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="todo")  # todo | in_progress | completed
    priority = db.Column(db.String(10), default="medium")  # low | medium | high
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)
    github_issue_number = db.Column(db.Integer, nullable=True)
    github_issue_url = db.Column(db.String(500), nullable=True)
    github_repo = db.Column(db.String(200), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "project_id": self.project_id,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "github_issue_number": self.github_issue_number,
            "github_issue_url": self.github_issue_url,
            "github_repo": self.github_repo,
        }


class GitHubConnection(db.Model):
    """Stores the OAuth token and selected repo. Single-row table."""
    id = db.Column(db.Integer, primary_key=True)
    access_token = db.Column(db.String(200), nullable=False)
    github_username = db.Column(db.String(100), default="")
    github_avatar = db.Column(db.String(500), default="")
    selected_repo = db.Column(db.String(200), default="")  # "owner/repo"

    def to_dict(self):
        return {
            "connected": True,
            "username": self.github_username,
            "avatar": self.github_avatar,
            "selected_repo": self.selected_repo,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_github_connection():
    return GitHubConnection.query.first()


def github_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


PRIORITY_TO_LABEL = {"high": "priority: high", "medium": "priority: medium", "low": "priority: low"}
STATUS_TO_GH_STATE = {"completed": "closed"}  # anything else -> open


# ---------------------------------------------------------------------------
# Create tables & seed data
# ---------------------------------------------------------------------------

with app.app_context():
    db.create_all()

    if Project.query.count() == 0:
        colors = ["#6366f1", "#ec4899", "#14b8a6", "#f59e0b", "#3b82f6"]
        seed_projects = [
            ("Data Pipeline", "ETL pipeline for experiment logs"),
            ("Web Portal", "Internal collaboration portal"),
            ("ML Training", "Model training automation"),
            ("Documentation", "Technical docs & guides"),
            ("Infrastructure", "Cloud & container orchestration"),
        ]
        for i, (name, desc) in enumerate(seed_projects):
            p = Project(name=name, description=desc, color=colors[i])
            db.session.add(p)
        db.session.flush()

        seed_tasks = [
            ("Design schema for raw data ingestion", "todo", "high", 1),
            ("Implement Kafka consumer", "in_progress", "high", 1),
            ("Write unit tests for transformer", "todo", "medium", 1),
            ("Set up monitoring dashboards", "completed", "low", 1),
            ("Create React component library", "completed", "high", 2),
            ("Implement authentication flow", "in_progress", "high", 2),
            ("Design landing page", "completed", "medium", 2),
            ("Build REST API endpoints", "completed", "high", 2),
            ("Prepare training dataset", "completed", "high", 3),
            ("Hyperparameter sweep", "in_progress", "medium", 3),
            ("Evaluate model accuracy", "todo", "high", 3),
            ("Write API reference docs", "in_progress", "medium", 4),
            ("Create onboarding guide", "todo", "low", 4),
            ("Dockerize all services", "completed", "high", 5),
            ("Set up CI/CD pipeline", "in_progress", "high", 5),
            ("Configure auto-scaling", "todo", "medium", 5),
        ]
        for title, status, priority, pid in seed_tasks:
            t = Task(
                title=title,
                status=status,
                priority=priority,
                project_id=pid,
                completed_at=datetime.now(timezone.utc) if status == "completed" else None,
            )
            db.session.add(t)
        db.session.commit()


# ---------------------------------------------------------------------------
# API Routes — Projects
# ---------------------------------------------------------------------------

@app.route("/api/projects", methods=["GET"])
def get_projects():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return jsonify([p.to_dict() for p in projects])


@app.route("/api/projects", methods=["POST"])
def create_project():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Name is required"}), 400
    project = Project(
        name=data["name"],
        description=data.get("description", ""),
        color=data.get("color", "#6366f1"),
    )
    db.session.add(project)
    db.session.commit()
    return jsonify(project.to_dict()), 201


@app.route("/api/projects/<int:project_id>", methods=["DELETE"])
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200


# ---------------------------------------------------------------------------
# API Routes — Tasks
# ---------------------------------------------------------------------------

@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    project_id = request.args.get("project_id", type=int)
    query = Task.query
    if project_id:
        query = query.filter_by(project_id=project_id)
    tasks = query.order_by(Task.created_at.desc()).all()
    return jsonify([t.to_dict() for t in tasks])


@app.route("/api/tasks", methods=["POST"])
def create_task():
    data = request.get_json()
    if not data or not data.get("title") or not data.get("project_id"):
        return jsonify({"error": "title and project_id are required"}), 400
    task = Task(
        title=data["title"],
        description=data.get("description", ""),
        status=data.get("status", "todo"),
        priority=data.get("priority", "medium"),
        project_id=data["project_id"],
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@app.route("/api/tasks/<int:task_id>", methods=["PATCH"])
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400
    for field in ("title", "description", "status", "priority"):
        if field in data:
            setattr(task, field, data[field])
    if "status" in data:
        if data["status"] == "completed" and not task.completed_at:
            task.completed_at = datetime.now(timezone.utc)
        elif data["status"] != "completed":
            task.completed_at = None
    db.session.commit()

    # If this task is linked to a GitHub issue, sync the state
    if task.github_issue_number and task.github_repo:
        conn = get_github_connection()
        if conn and conn.access_token:
            _sync_task_to_github(task, conn.access_token)

    return jsonify(task.to_dict())


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200


# ---------------------------------------------------------------------------
# API Routes — Dashboard Stats
# ---------------------------------------------------------------------------

@app.route("/api/stats", methods=["GET"])
def get_stats():
    total_tasks = Task.query.count()
    completed = Task.query.filter_by(status="completed").count()
    in_progress = Task.query.filter_by(status="in_progress").count()
    todo = Task.query.filter_by(status="todo").count()
    high_priority = Task.query.filter(Task.priority == "high", Task.status != "completed").count()
    projects = Project.query.count()

    return jsonify({
        "total_tasks": total_tasks,
        "completed": completed,
        "in_progress": in_progress,
        "todo": todo,
        "high_priority_pending": high_priority,
        "total_projects": projects,
        "completion_rate": round((completed / total_tasks * 100), 1) if total_tasks else 0,
    })


# ===========================================================================
# GitHub OAuth Flow
# ===========================================================================

@app.route("/api/github/auth")
def github_auth():
    """Redirect the user to GitHub's OAuth authorize page."""
    client_id = app.config["GITHUB_CLIENT_ID"]
    if not client_id:
        return jsonify({"error": "GITHUB_CLIENT_ID not configured"}), 500

    state = secrets.token_urlsafe(32)
    session["github_oauth_state"] = state

    params = (
        f"?client_id={client_id}"
        f"&scope=repo"
        f"&state={state}"
        f"&redirect_uri={app.config['FRONTEND_URL']}/github/callback"
    )
    return redirect(GITHUB_AUTHORIZE_URL + params)


@app.route("/api/github/callback")
def github_callback():
    """Exchange the temporary code for an access token."""
    code = request.args.get("code")
    state = request.args.get("state")

    if not code:
        return jsonify({"error": "Missing code parameter"}), 400

    # Verify state to prevent CSRF
    saved_state = session.pop("github_oauth_state", None)
    if not saved_state or state != saved_state:
        return jsonify({"error": "State mismatch — session may have expired, please try again"}), 403

    client_id = app.config["GITHUB_CLIENT_ID"]
    client_secret = app.config["GITHUB_CLIENT_SECRET"]

    # Exchange code for token
    try:
        resp = http_requests.post(
            GITHUB_TOKEN_URL,
            json={"client_id": client_id, "client_secret": client_secret, "code": code},
            headers={"Accept": "application/json"},
            timeout=10,
        )
        token_data = resp.json()
    except (http_requests.RequestException, ValueError) as exc:
        log.warning("GitHub token exchange failed: %s", exc)
        return jsonify({"error": "Failed to communicate with GitHub"}), 502
    access_token = token_data.get("access_token")

    if not access_token:
        return jsonify({"error": "Failed to get access token"}), 400

    # Fetch user info
    try:
        user_resp = http_requests.get(
            f"{GITHUB_API}/user",
            headers=github_headers(access_token),
            timeout=10,
        )
        if user_resp.status_code != 200:
            return jsonify({"error": "Failed to fetch GitHub user info"}), 502
        user = user_resp.json()
    except (http_requests.RequestException, ValueError) as exc:
        log.warning("GitHub user info fetch failed: %s", exc)
        return jsonify({"error": "Failed to communicate with GitHub"}), 502

    # Store (upsert single row)
    conn = get_github_connection()
    if conn:
        conn.access_token = access_token
        conn.github_username = user.get("login", "")
        conn.github_avatar = user.get("avatar_url", "")
    else:
        conn = GitHubConnection(
            access_token=access_token,
            github_username=user.get("login", ""),
            github_avatar=user.get("avatar_url", ""),
        )
        db.session.add(conn)
    db.session.commit()

    return jsonify({"ok": True, "username": conn.github_username})


@app.route("/api/github/status")
def github_status():
    """Return current connection status."""
    conn = get_github_connection()
    if not conn:
        return jsonify({"connected": False})
    return jsonify(conn.to_dict())


@app.route("/api/github/disconnect", methods=["POST"])
def github_disconnect():
    """Remove the stored GitHub connection."""
    conn = get_github_connection()
    if conn:
        db.session.delete(conn)
        db.session.commit()
    return jsonify({"connected": False})


# ===========================================================================
# GitHub — Repos
# ===========================================================================

@app.route("/api/github/repos")
def github_repos():
    """List repos the authenticated user has push access to."""
    conn = get_github_connection()
    if not conn:
        return jsonify({"error": "Not connected to GitHub"}), 401

    repos = []
    page = 1
    while page <= 10:  # cap at 10 pages (1000 repos) to prevent unbounded loops
        try:
            resp = http_requests.get(
                f"{GITHUB_API}/user/repos",
                headers=github_headers(conn.access_token),
                params={"per_page": 100, "page": page, "sort": "updated", "affiliation": "owner,collaborator,organization_member"},
                timeout=10,
            )
        except http_requests.RequestException as exc:
            log.warning("GitHub repos fetch failed: %s", exc)
            return jsonify({"error": "Failed to communicate with GitHub"}), 502
        if resp.status_code != 200:
            detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            return jsonify({"error": "GitHub API error", "details": detail}), resp.status_code
        try:
            batch = resp.json()
        except ValueError:
            return jsonify({"error": "Invalid response from GitHub"}), 502
        if not batch:
            break
        repos.extend([
            {"full_name": r["full_name"], "private": r["private"], "description": r.get("description", "")}
            for r in batch
            if r.get("permissions", {}).get("push", False)
        ])
        page += 1
        if len(batch) < 100:
            break

    return jsonify(repos)


@app.route("/api/github/repo", methods=["PUT"])
def set_github_repo():
    """Set the selected repo for issue sync."""
    conn = get_github_connection()
    if not conn:
        return jsonify({"error": "Not connected to GitHub"}), 401
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400
    repo = data.get("repo", "")
    conn.selected_repo = repo
    db.session.commit()
    return jsonify(conn.to_dict())


# ===========================================================================
# GitHub — Push / Sync Issues
# ===========================================================================

def _build_issue_body(task):
    parts = []
    if task.description:
        parts.append(task.description)
    parts.append(f"\n---\n*Synced from Project Dashboard (task #{task.id})*")
    return "\n".join(parts)


def _sync_task_to_github(task, token):
    """Push current task status to the linked GitHub issue."""
    try:
        gh_state = STATUS_TO_GH_STATE.get(task.status, "open")
        http_requests.patch(
            f"{GITHUB_API}/repos/{task.github_repo}/issues/{task.github_issue_number}",
            headers=github_headers(token),
            json={"state": gh_state},
            timeout=10,
        )
    except Exception as exc:
        log.warning("Best-effort GitHub sync failed for task %s: %s", task.id, exc)


@app.route("/api/tasks/<int:task_id>/push-to-github", methods=["POST"])
def push_task_to_github(task_id):
    """Create a GitHub issue from a task."""
    task = Task.query.get_or_404(task_id)
    conn = get_github_connection()
    if not conn:
        return jsonify({"error": "Not connected to GitHub"}), 401
    if not conn.selected_repo:
        return jsonify({"error": "No repository selected"}), 400
    if task.github_issue_number:
        return jsonify({"error": "Task already linked to an issue", "issue_url": task.github_issue_url}), 409

    # Create issue
    labels = []
    label_name = PRIORITY_TO_LABEL.get(task.priority)
    if label_name:
        labels.append(label_name)

    project = Project.query.get(task.project_id)
    title_prefix = f"[{project.name}] " if project else ""

    try:
        resp = http_requests.post(
            f"{GITHUB_API}/repos/{conn.selected_repo}/issues",
            headers=github_headers(conn.access_token),
            json={
                "title": f"{title_prefix}{task.title}",
                "body": _build_issue_body(task),
                "labels": labels,
            },
            timeout=10,
        )
    except http_requests.RequestException as exc:
        log.warning("GitHub issue creation failed: %s", exc)
        return jsonify({"error": "Failed to communicate with GitHub"}), 502

    if resp.status_code not in (200, 201):
        detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        return jsonify({"error": "GitHub API error", "details": detail}), resp.status_code

    try:
        issue = resp.json()
    except ValueError:
        return jsonify({"error": "Invalid response from GitHub"}), 502
    task.github_issue_number = issue["number"]
    task.github_issue_url = issue["html_url"]
    task.github_repo = conn.selected_repo

    # If task is already completed, close the issue right away
    if task.status == "completed":
        _sync_task_to_github(task, conn.access_token)

    db.session.commit()
    return jsonify(task.to_dict()), 201


@app.route("/api/tasks/<int:task_id>/sync-github", methods=["POST"])
def sync_task_from_github(task_id):
    """Pull the latest issue state from GitHub into the task."""
    task = Task.query.get_or_404(task_id)
    if not task.github_issue_number or not task.github_repo:
        return jsonify({"error": "Task is not linked to a GitHub issue"}), 400

    conn = get_github_connection()
    if not conn:
        return jsonify({"error": "Not connected to GitHub"}), 401

    try:
        resp = http_requests.get(
            f"{GITHUB_API}/repos/{task.github_repo}/issues/{task.github_issue_number}",
            headers=github_headers(conn.access_token),
            timeout=10,
        )
    except http_requests.RequestException as exc:
        log.warning("GitHub issue sync failed: %s", exc)
        return jsonify({"error": "Failed to communicate with GitHub"}), 502
    if resp.status_code != 200:
        detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        return jsonify({"error": "GitHub API error", "details": detail}), resp.status_code

    try:
        issue = resp.json()
    except ValueError:
        return jsonify({"error": "Invalid response from GitHub"}), 502
    gh_state = issue.get("state", "open")

    if gh_state == "closed" and task.status != "completed":
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)
    elif gh_state == "open" and task.status == "completed":
        task.status = "todo"
        task.completed_at = None

    db.session.commit()
    return jsonify(task.to_dict())


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)
