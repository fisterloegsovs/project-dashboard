import logging
import os
import secrets
from datetime import datetime, timezone, timedelta
from functools import wraps

import bcrypt
import jwt
from flask import Flask, jsonify, request, redirect, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
import requests as http_requests

log = logging.getLogger(__name__)

app = Flask(__name__)

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
CORS(app, origins=[FRONTEND_URL], supports_credentials=True)

basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'dashboard.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET", secrets.token_hex(32))
app.config["JWT_EXPIRY_HOURS"] = 24

# GitHub OAuth configuration
app.config["GITHUB_CLIENT_ID"] = os.environ.get("GITHUB_CLIENT_ID", "")
app.config["GITHUB_CLIENT_SECRET"] = os.environ.get("GITHUB_CLIENT_SECRET", "")
app.config["FRONTEND_URL"] = FRONTEND_URL

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API = "https://api.github.com"

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins=FRONTEND_URL, async_mode="threading")


# ===========================================================================
# Models
# ===========================================================================

# --- User ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    display_name = db.Column(db.String(120), default="")
    avatar_color = db.Column(db.String(7), default="#6366f1")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    team_memberships = db.relationship("TeamMembership", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, password):
        return bcrypt.checkpw(password.encode(), self.password_hash.encode())

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "display_name": self.display_name or self.username,
            "avatar_color": self.avatar_color,
            "created_at": self.created_at.isoformat(),
        }


# --- Team ---

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    color = db.Column(db.String(7), default="#6366f1")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Relationships
    memberships = db.relationship("TeamMembership", backref="team", lazy=True, cascade="all, delete-orphan")
    projects = db.relationship("Project", backref="team", lazy=True)

    def to_dict(self, include_members=False):
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "member_count": len(self.memberships),
        }
        if include_members:
            result["members"] = [m.to_dict() for m in self.memberships]
        return result


# --- Team Membership (with roles) ---

ROLES = {"admin", "member", "viewer"}

class TeamMembership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False)
    role = db.Column(db.String(20), default="member")  # admin | member | viewer
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint("user_id", "team_id", name="uq_user_team"),)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "team_id": self.team_id,
            "role": self.role,
            "joined_at": self.joined_at.isoformat(),
            "user": self.user.to_dict() if self.user else None,
        }


# --- Project (updated with team_id) ---

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    color = db.Column(db.String(7), default="#6366f1")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    tasks = db.relationship("Task", backref="project", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "created_at": self.created_at.isoformat(),
            "team_id": self.team_id,
            "created_by": self.created_by,
            "task_count": len(self.tasks),
            "completed_count": sum(1 for t in self.tasks if t.status == "completed"),
        }


# --- Task (updated with assigned_to) ---

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="todo")  # todo | in_progress | completed
    priority = db.Column(db.String(10), default="medium")  # low | medium | high
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)
    github_issue_number = db.Column(db.Integer, nullable=True)
    github_issue_url = db.Column(db.String(500), nullable=True)
    github_repo = db.Column(db.String(200), nullable=True)

    assignee = db.relationship("User", foreign_keys=[assigned_to], backref="assigned_tasks")
    creator = db.relationship("User", foreign_keys=[created_by], backref="created_tasks")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "project_id": self.project_id,
            "assigned_to": self.assigned_to,
            "assignee": self.assignee.to_dict() if self.assignee else None,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "github_issue_number": self.github_issue_number,
            "github_issue_url": self.github_issue_url,
            "github_repo": self.github_repo,
        }


# --- Video Call ---

class VideoCall(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.String(64), unique=True, nullable=False)
    title = db.Column(db.String(200), default="")
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default="active")  # active | ended

    creator = db.relationship("User", backref="created_calls")

    def to_dict(self):
        return {
            "id": self.id,
            "room_id": self.room_id,
            "title": self.title,
            "team_id": self.team_id,
            "created_by": self.created_by,
            "creator": self.creator.to_dict() if self.creator else None,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "status": self.status,
        }


# --- GitHub Connection ---

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


# ===========================================================================
# Auth helpers
# ===========================================================================

def create_token(user_id):
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=app.config["JWT_EXPIRY_HOURS"]),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, app.config["JWT_SECRET"], algorithm="HS256")


def decode_token(token):
    try:
        payload = jwt.decode(token, app.config["JWT_SECRET"], algorithms=["HS256"])
        return payload["user_id"]
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def get_current_user():
    """Extract user from Authorization header. Returns User or None."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    user_id = decode_token(token)
    if not user_id:
        return None
    return User.query.get(user_id)


def auth_required(f):
    """Decorator: require a valid JWT token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


# ===========================================================================
# RBAC helpers
# ===========================================================================

ROLE_HIERARCHY = {"admin": 3, "member": 2, "viewer": 1}


def get_user_role_in_team(user_id, team_id):
    """Get a user's role in a team. Returns role string or None."""
    membership = TeamMembership.query.filter_by(user_id=user_id, team_id=team_id).first()
    return membership.role if membership else None


def require_team_role(min_role):
    """Decorator factory: require at least `min_role` in the team.
    The team_id must be provided as a route parameter or in the request body.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = request.current_user
            # Try to get team_id from route params, query params, or body
            team_id = kwargs.get("team_id")
            if not team_id:
                team_id = request.args.get("team_id", type=int)
            if not team_id:
                data = request.get_json(silent=True) or {}
                team_id = data.get("team_id")
            if not team_id:
                return jsonify({"error": "team_id is required"}), 400

            role = get_user_role_in_team(user.id, team_id)
            if not role:
                return jsonify({"error": "You are not a member of this team"}), 403
            if ROLE_HIERARCHY.get(role, 0) < ROLE_HIERARCHY.get(min_role, 0):
                return jsonify({"error": f"Requires at least '{min_role}' role"}), 403

            request.user_team_role = role
            return f(*args, **kwargs)
        return decorated
    return decorator


def can_modify_resource(user, resource_team_id):
    """Check if user has at least 'member' role in the resource's team.
    If resource has no team, allow any authenticated user.
    """
    if not resource_team_id:
        return True
    role = get_user_role_in_team(user.id, resource_team_id)
    if not role:
        return False
    return ROLE_HIERARCHY.get(role, 0) >= ROLE_HIERARCHY["member"]


def can_view_resource(user, resource_team_id):
    """Check if user has at least 'viewer' role in the resource's team.
    If resource has no team, allow any authenticated user.
    """
    if not resource_team_id:
        return True
    role = get_user_role_in_team(user.id, resource_team_id)
    return role is not None


# ===========================================================================
# GitHub helpers (unchanged)
# ===========================================================================

def get_github_connection():
    return GitHubConnection.query.first()


def github_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


PRIORITY_TO_LABEL = {"high": "priority: high", "medium": "priority: medium", "low": "priority: low"}
STATUS_TO_GH_STATE = {"completed": "closed"}


# ===========================================================================
# Create tables & seed data
# ===========================================================================

with app.app_context():
    db.create_all()

    # Seed: create a default admin user if none exists
    if User.query.count() == 0:
        admin = User(
            username="admin",
            email="admin@dashboard.local",
            display_name="Admin",
            avatar_color="#6366f1",
        )
        admin.set_password("admin")
        db.session.add(admin)
        db.session.flush()

        # Create a default team
        default_team = Team(
            name="General",
            description="Default team for all projects",
            color="#6366f1",
            created_by=admin.id,
        )
        db.session.add(default_team)
        db.session.flush()

        # Add admin to the default team
        membership = TeamMembership(
            user_id=admin.id,
            team_id=default_team.id,
            role="admin",
        )
        db.session.add(membership)
        db.session.flush()

        # Seed projects (assign to default team)
        colors = ["#6366f1", "#ec4899", "#14b8a6", "#f59e0b", "#3b82f6"]
        seed_projects = [
            ("Data Pipeline", "ETL pipeline for experiment logs"),
            ("Web Portal", "Internal collaboration portal"),
            ("ML Training", "Model training automation"),
            ("Documentation", "Technical docs & guides"),
            ("Infrastructure", "Cloud & container orchestration"),
        ]
        for i, (name, desc) in enumerate(seed_projects):
            p = Project(name=name, description=desc, color=colors[i],
                        team_id=default_team.id, created_by=admin.id)
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
                created_by=admin.id,
                completed_at=datetime.now(timezone.utc) if status == "completed" else None,
            )
            db.session.add(t)
        db.session.commit()
        log.info("Seeded database with admin user (admin/admin), default team, and sample data")


# ===========================================================================
# API Routes — Auth
# ===========================================================================

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    display_name = data.get("display_name", "").strip()

    if not username or not email or not password:
        return jsonify({"error": "username, email, and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({"error": "Username or email already taken"}), 409

    avatar_colors = ["#6366f1", "#ec4899", "#14b8a6", "#f59e0b", "#3b82f6", "#ef4444", "#8b5cf6"]
    user = User(
        username=username,
        email=email,
        display_name=display_name or username,
        avatar_color=avatar_colors[hash(username) % len(avatar_colors)],
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    # Auto-join the "General" team as member if it exists
    general_team = Team.query.filter_by(name="General").first()
    if general_team:
        m = TeamMembership(user_id=user.id, team_id=general_team.id, role="member")
        db.session.add(m)

    db.session.commit()

    token = create_token(user.id)
    return jsonify({"token": token, "user": user.to_dict()}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    # Allow login by username or email
    user = User.query.filter(
        (User.username == username) | (User.email == username)
    ).first()

    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = create_token(user.id)
    return jsonify({"token": token, "user": user.to_dict()})


@app.route("/api/auth/me", methods=["GET"])
@auth_required
def get_me():
    user = request.current_user
    teams = []
    for m in user.team_memberships:
        t = m.team
        teams.append({
            "id": t.id,
            "name": t.name,
            "color": t.color,
            "role": m.role,
        })
    result = user.to_dict()
    result["teams"] = teams
    return jsonify(result)


# ===========================================================================
# API Routes — Teams
# ===========================================================================

@app.route("/api/teams", methods=["GET"])
@auth_required
def get_teams():
    """Get all teams the current user is a member of."""
    user = request.current_user
    memberships = TeamMembership.query.filter_by(user_id=user.id).all()
    teams = []
    for m in memberships:
        t = m.team.to_dict()
        t["role"] = m.role
        teams.append(t)
    return jsonify(teams)


@app.route("/api/teams", methods=["POST"])
@auth_required
def create_team():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Name is required"}), 400

    user = request.current_user
    team = Team(
        name=data["name"],
        description=data.get("description", ""),
        color=data.get("color", "#6366f1"),
        created_by=user.id,
    )
    db.session.add(team)
    db.session.flush()

    # Creator is automatically admin
    membership = TeamMembership(user_id=user.id, team_id=team.id, role="admin")
    db.session.add(membership)
    db.session.commit()

    result = team.to_dict()
    result["role"] = "admin"
    return jsonify(result), 201


@app.route("/api/teams/<int:team_id>", methods=["GET"])
@auth_required
def get_team(team_id):
    team = Team.query.get_or_404(team_id)
    user = request.current_user
    if not can_view_resource(user, team_id):
        return jsonify({"error": "Access denied"}), 403
    return jsonify(team.to_dict(include_members=True))


@app.route("/api/teams/<int:team_id>", methods=["PATCH"])
@auth_required
@require_team_role("admin")
def update_team(team_id):
    team = Team.query.get_or_404(team_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400
    for field in ("name", "description", "color"):
        if field in data:
            setattr(team, field, data[field])
    db.session.commit()
    return jsonify(team.to_dict())


@app.route("/api/teams/<int:team_id>", methods=["DELETE"])
@auth_required
@require_team_role("admin")
def delete_team(team_id):
    team = Team.query.get_or_404(team_id)
    db.session.delete(team)
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200


@app.route("/api/teams/<int:team_id>/members", methods=["POST"])
@auth_required
@require_team_role("admin")
def add_team_member(team_id):
    """Add a user to a team. Body: { username, role }"""
    Team.query.get_or_404(team_id)
    data = request.get_json()
    if not data or not data.get("username"):
        return jsonify({"error": "username is required"}), 400

    target_user = User.query.filter_by(username=data["username"]).first()
    if not target_user:
        return jsonify({"error": "User not found"}), 404

    existing = TeamMembership.query.filter_by(user_id=target_user.id, team_id=team_id).first()
    if existing:
        return jsonify({"error": "User is already a member of this team"}), 409

    role = data.get("role", "member")
    if role not in ROLES:
        return jsonify({"error": f"Invalid role. Must be one of: {', '.join(ROLES)}"}), 400

    m = TeamMembership(user_id=target_user.id, team_id=team_id, role=role)
    db.session.add(m)
    db.session.commit()
    return jsonify(m.to_dict()), 201


@app.route("/api/teams/<int:team_id>/members/<int:user_id>", methods=["PATCH"])
@auth_required
@require_team_role("admin")
def update_team_member(team_id, user_id):
    """Update a member's role. Body: { role }"""
    m = TeamMembership.query.filter_by(user_id=user_id, team_id=team_id).first()
    if not m:
        return jsonify({"error": "Membership not found"}), 404
    data = request.get_json()
    if not data or "role" not in data:
        return jsonify({"error": "role is required"}), 400
    if data["role"] not in ROLES:
        return jsonify({"error": f"Invalid role. Must be one of: {', '.join(ROLES)}"}), 400
    m.role = data["role"]
    db.session.commit()
    return jsonify(m.to_dict())


@app.route("/api/teams/<int:team_id>/members/<int:user_id>", methods=["DELETE"])
@auth_required
@require_team_role("admin")
def remove_team_member(team_id, user_id):
    """Remove a user from a team."""
    m = TeamMembership.query.filter_by(user_id=user_id, team_id=team_id).first()
    if not m:
        return jsonify({"error": "Membership not found"}), 404
    # Prevent removing the last admin
    if m.role == "admin":
        admin_count = TeamMembership.query.filter_by(team_id=team_id, role="admin").count()
        if admin_count <= 1:
            return jsonify({"error": "Cannot remove the last admin from a team"}), 400
    db.session.delete(m)
    db.session.commit()
    return jsonify({"message": "Removed"}), 200


# ===========================================================================
# API Routes — Projects (updated with team + RBAC)
# ===========================================================================

@app.route("/api/projects", methods=["GET"])
@auth_required
def get_projects():
    user = request.current_user
    team_id = request.args.get("team_id", type=int)

    if team_id:
        if not can_view_resource(user, team_id):
            return jsonify({"error": "Access denied"}), 403
        projects = Project.query.filter_by(team_id=team_id).order_by(Project.created_at.desc()).all()
    else:
        # Get all projects from user's teams + unassigned projects they created
        user_team_ids = [m.team_id for m in user.team_memberships]
        projects = Project.query.filter(
            (Project.team_id.in_(user_team_ids)) | (Project.created_by == user.id)
        ).order_by(Project.created_at.desc()).all()

    return jsonify([p.to_dict() for p in projects])


@app.route("/api/projects", methods=["POST"])
@auth_required
def create_project():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Name is required"}), 400

    user = request.current_user
    team_id = data.get("team_id")

    if team_id:
        if not can_modify_resource(user, team_id):
            return jsonify({"error": "You need at least 'member' role to create projects in this team"}), 403

    project = Project(
        name=data["name"],
        description=data.get("description", ""),
        color=data.get("color", "#6366f1"),
        team_id=team_id,
        created_by=user.id,
    )
    db.session.add(project)
    db.session.commit()
    return jsonify(project.to_dict()), 201


@app.route("/api/projects/<int:project_id>", methods=["DELETE"])
@auth_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    user = request.current_user
    if not can_modify_resource(user, project.team_id):
        return jsonify({"error": "Access denied"}), 403
    db.session.delete(project)
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200


# ===========================================================================
# API Routes — Tasks (updated with assignment + RBAC)
# ===========================================================================

@app.route("/api/tasks", methods=["GET"])
@auth_required
def get_tasks():
    user = request.current_user
    project_id = request.args.get("project_id", type=int)
    team_id = request.args.get("team_id", type=int)

    query = Task.query
    if project_id:
        query = query.filter_by(project_id=project_id)
    elif team_id:
        if not can_view_resource(user, team_id):
            return jsonify({"error": "Access denied"}), 403
        project_ids = [p.id for p in Project.query.filter_by(team_id=team_id).all()]
        query = query.filter(Task.project_id.in_(project_ids))
    else:
        # Only tasks in user's teams
        user_team_ids = [m.team_id for m in user.team_memberships]
        team_project_ids = [p.id for p in Project.query.filter(
            (Project.team_id.in_(user_team_ids)) | (Project.created_by == user.id)
        ).all()]
        query = query.filter(Task.project_id.in_(team_project_ids))

    tasks = query.order_by(Task.created_at.desc()).all()
    return jsonify([t.to_dict() for t in tasks])


@app.route("/api/tasks", methods=["POST"])
@auth_required
def create_task():
    data = request.get_json()
    if not data or not data.get("title") or not data.get("project_id"):
        return jsonify({"error": "title and project_id are required"}), 400

    user = request.current_user
    project = Project.query.get(data["project_id"])
    if not project:
        return jsonify({"error": "Project not found"}), 404
    if not can_modify_resource(user, project.team_id):
        return jsonify({"error": "Access denied"}), 403

    task = Task(
        title=data["title"],
        description=data.get("description", ""),
        status=data.get("status", "todo"),
        priority=data.get("priority", "medium"),
        project_id=data["project_id"],
        assigned_to=data.get("assigned_to"),
        created_by=user.id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@app.route("/api/tasks/<int:task_id>", methods=["PATCH"])
@auth_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    user = request.current_user
    project = Project.query.get(task.project_id)
    if not can_modify_resource(user, project.team_id if project else None):
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400
    for field in ("title", "description", "status", "priority", "assigned_to"):
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
@auth_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    user = request.current_user
    project = Project.query.get(task.project_id)
    if not can_modify_resource(user, project.team_id if project else None):
        return jsonify({"error": "Access denied"}), 403
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200


# ===========================================================================
# API Routes — Dashboard Stats
# ===========================================================================

@app.route("/api/stats", methods=["GET"])
@auth_required
def get_stats():
    user = request.current_user
    team_id = request.args.get("team_id", type=int)

    if team_id:
        project_ids = [p.id for p in Project.query.filter_by(team_id=team_id).all()]
        base_query = Task.query.filter(Task.project_id.in_(project_ids))
    else:
        user_team_ids = [m.team_id for m in user.team_memberships]
        team_project_ids = [p.id for p in Project.query.filter(
            (Project.team_id.in_(user_team_ids)) | (Project.created_by == user.id)
        ).all()]
        base_query = Task.query.filter(Task.project_id.in_(team_project_ids))

    total_tasks = base_query.count()
    completed = base_query.filter(Task.status == "completed").count()
    in_progress = base_query.filter(Task.status == "in_progress").count()
    todo = base_query.filter(Task.status == "todo").count()
    high_priority = base_query.filter(Task.priority == "high", Task.status != "completed").count()
    projects = len(set(t.project_id for t in base_query.all()))

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
# API Routes — Video Calls
# ===========================================================================

@app.route("/api/calls", methods=["GET"])
@auth_required
def get_calls():
    """Get active calls for the user's teams."""
    user = request.current_user
    team_id = request.args.get("team_id", type=int)

    if team_id:
        if not can_view_resource(user, team_id):
            return jsonify({"error": "Access denied"}), 403
        calls = VideoCall.query.filter_by(team_id=team_id, status="active").order_by(VideoCall.started_at.desc()).all()
    else:
        user_team_ids = [m.team_id for m in user.team_memberships]
        calls = VideoCall.query.filter(
            VideoCall.team_id.in_(user_team_ids),
            VideoCall.status == "active"
        ).order_by(VideoCall.started_at.desc()).all()

    return jsonify([c.to_dict() for c in calls])


@app.route("/api/calls", methods=["POST"])
@auth_required
def create_call():
    """Start a new video call."""
    data = request.get_json() or {}
    user = request.current_user
    team_id = data.get("team_id")

    if team_id and not can_view_resource(user, team_id):
        return jsonify({"error": "Access denied"}), 403

    call = VideoCall(
        room_id=secrets.token_urlsafe(16),
        title=data.get("title", f"{user.display_name or user.username}'s call"),
        team_id=team_id,
        created_by=user.id,
    )
    db.session.add(call)
    db.session.commit()
    return jsonify(call.to_dict()), 201


@app.route("/api/calls/<int:call_id>/end", methods=["POST"])
@auth_required
def end_call(call_id):
    call = VideoCall.query.get_or_404(call_id)
    user = request.current_user
    if call.created_by != user.id:
        return jsonify({"error": "Only the call creator can end it"}), 403
    call.status = "ended"
    call.ended_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(call.to_dict())


# ===========================================================================
# WebRTC Signaling via Socket.IO
# ===========================================================================

# Track connected users per room: { room_id: { socket_id: user_dict } }
call_participants = {}


@socketio.on("connect")
def handle_connect():
    log.info("Socket connected: %s", request.sid)


@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    # Remove from all rooms
    for room_id, participants in list(call_participants.items()):
        if sid in participants:
            user_info = participants.pop(sid)
            emit("user-left", {"sid": sid, "user": user_info}, to=room_id)
            if not participants:
                del call_participants[room_id]
    log.info("Socket disconnected: %s", sid)


@socketio.on("join-call")
def handle_join_call(data):
    """Join a video call room. data: { room_id, token }"""
    room_id = data.get("room_id")
    token = data.get("token")

    if not room_id or not token:
        emit("error", {"message": "room_id and token are required"})
        return

    user_id = decode_token(token)
    if not user_id:
        emit("error", {"message": "Invalid token"})
        return

    user = User.query.get(user_id)
    if not user:
        emit("error", {"message": "User not found"})
        return

    join_room(room_id)

    if room_id not in call_participants:
        call_participants[room_id] = {}

    user_info = user.to_dict()
    existing_participants = list(call_participants[room_id].values())

    call_participants[room_id][request.sid] = user_info

    # Tell the joiner about existing participants
    emit("existing-participants", {"participants": existing_participants, "sids": list(call_participants[room_id].keys())})

    # Tell everyone else about the new user
    emit("user-joined", {"sid": request.sid, "user": user_info}, to=room_id, include_self=False)

    log.info("User %s joined call %s", user.username, room_id)


@socketio.on("leave-call")
def handle_leave_call(data):
    room_id = data.get("room_id")
    if not room_id:
        return

    leave_room(room_id)

    if room_id in call_participants and request.sid in call_participants[room_id]:
        user_info = call_participants[room_id].pop(request.sid)
        emit("user-left", {"sid": request.sid, "user": user_info}, to=room_id)
        if not call_participants[room_id]:
            del call_participants[room_id]


@socketio.on("offer")
def handle_offer(data):
    """Forward WebRTC offer to a specific peer. data: { target_sid, offer }"""
    emit("offer", {
        "from_sid": request.sid,
        "offer": data.get("offer"),
    }, to=data.get("target_sid"))


@socketio.on("answer")
def handle_answer(data):
    """Forward WebRTC answer to a specific peer. data: { target_sid, answer }"""
    emit("answer", {
        "from_sid": request.sid,
        "answer": data.get("answer"),
    }, to=data.get("target_sid"))


@socketio.on("ice-candidate")
def handle_ice_candidate(data):
    """Forward ICE candidate to a specific peer. data: { target_sid, candidate }"""
    emit("ice-candidate", {
        "from_sid": request.sid,
        "candidate": data.get("candidate"),
    }, to=data.get("target_sid"))


# ===========================================================================
# GitHub OAuth Flow (unchanged)
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

    saved_state = session.pop("github_oauth_state", None)
    if not saved_state or state != saved_state:
        return jsonify({"error": "State mismatch — session may have expired, please try again"}), 403

    client_id = app.config["GITHUB_CLIENT_ID"]
    client_secret = app.config["GITHUB_CLIENT_SECRET"]

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

    try:
        user_resp = http_requests.get(
            f"{GITHUB_API}/user",
            headers=github_headers(access_token),
            timeout=10,
        )
        if user_resp.status_code != 200:
            return jsonify({"error": "Failed to fetch GitHub user info"}), 502
        gh_user = user_resp.json()
    except (http_requests.RequestException, ValueError) as exc:
        log.warning("GitHub user info fetch failed: %s", exc)
        return jsonify({"error": "Failed to communicate with GitHub"}), 502

    conn = get_github_connection()
    if conn:
        conn.access_token = access_token
        conn.github_username = gh_user.get("login", "")
        conn.github_avatar = gh_user.get("avatar_url", "")
    else:
        conn = GitHubConnection(
            access_token=access_token,
            github_username=gh_user.get("login", ""),
            github_avatar=gh_user.get("avatar_url", ""),
        )
        db.session.add(conn)
    db.session.commit()

    return jsonify({"ok": True, "username": conn.github_username})


@app.route("/api/github/status")
def github_status():
    conn = get_github_connection()
    if not conn:
        return jsonify({"connected": False})
    return jsonify(conn.to_dict())


@app.route("/api/github/disconnect", methods=["POST"])
def github_disconnect():
    conn = get_github_connection()
    if conn:
        db.session.delete(conn)
        db.session.commit()
    return jsonify({"connected": False})


@app.route("/api/github/repos")
def github_repos():
    conn = get_github_connection()
    if not conn:
        return jsonify({"error": "Not connected to GitHub"}), 401

    repos = []
    page = 1
    while page <= 10:
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
# GitHub — Push / Sync Issues (unchanged)
# ===========================================================================

def _build_issue_body(task):
    parts = []
    if task.description:
        parts.append(task.description)
    parts.append(f"\n---\n*Synced from Project Dashboard (task #{task.id})*")
    return "\n".join(parts)


def _sync_task_to_github(task, token):
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
@auth_required
def push_task_to_github(task_id):
    task = Task.query.get_or_404(task_id)
    conn = get_github_connection()
    if not conn:
        return jsonify({"error": "Not connected to GitHub"}), 401
    if not conn.selected_repo:
        return jsonify({"error": "No repository selected"}), 400
    if task.github_issue_number:
        return jsonify({"error": "Task already linked to an issue", "issue_url": task.github_issue_url}), 409

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

    if task.status == "completed":
        _sync_task_to_github(task, conn.access_token)

    db.session.commit()
    return jsonify(task.to_dict()), 201


@app.route("/api/tasks/<int:task_id>/sync-github", methods=["POST"])
@auth_required
def sync_task_from_github(task_id):
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


# ===========================================================================
# Users lookup (for assignment)
# ===========================================================================

@app.route("/api/users", methods=["GET"])
@auth_required
def get_users():
    """Search users. Optional query param: q (search), team_id (filter by team)."""
    q = request.args.get("q", "").strip()
    team_id = request.args.get("team_id", type=int)

    query = User.query
    if q:
        query = query.filter(
            (User.username.ilike(f"%{q}%")) | (User.display_name.ilike(f"%{q}%"))
        )
    if team_id:
        member_ids = [m.user_id for m in TeamMembership.query.filter_by(team_id=team_id).all()]
        query = query.filter(User.id.in_(member_ids))

    users = query.limit(50).all()
    return jsonify([u.to_dict() for u in users])


# ===========================================================================
# Run
# ===========================================================================

if __name__ == "__main__":
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)
