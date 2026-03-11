# Project Dashboard

A full-stack project management dashboard built with **Flask** (Python) and **React** (Vite), featuring GitHub OAuth integration for pushing tasks as GitHub issues.

## Features

- Kanban-style task board (To Do / In Progress / Completed)
- Multi-project support with color coding
- Live statistics dashboard
- Create, update, and delete projects and tasks
- Priority levels (low / medium / high)
- Dark and light themes with smooth transitions
- GitHub OAuth integration — push tasks as GitHub issues, sync status bidirectionally
- Responsive layout

## Quick Start

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

The API server starts at **http://localhost:5000**. A SQLite database (`dashboard.db`) is created automatically with sample data.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

The dev server starts at **http://localhost:5173** and proxies `/api` requests to the Flask backend.

## GitHub Integration (Optional)

The dashboard can connect to GitHub to push tasks as issues and sync their status.

### Setting Up GitHub OAuth

1. Go to **GitHub > Settings > Developer settings > OAuth Apps > New OAuth App**
2. Fill in the form:
   - **Application name:** Project Dashboard (or anything you like)
   - **Homepage URL:** `http://localhost:5173`
   - **Authorization callback URL:** `http://localhost:5173/github/callback`
3. Click **Register application**
4. Copy the **Client ID** and generate a **Client Secret**

### Environment Variables

Set these before starting the backend:

```bash
export GITHUB_CLIENT_ID="your_client_id_here"
export GITHUB_CLIENT_SECRET="your_client_secret_here"
# Optional — defaults shown:
# export FRONTEND_URL="http://localhost:5173"
# export SECRET_KEY="your-secret-key"
```

Or create a `.env` file in the `backend/` directory (you'll need `python-dotenv` for that approach).

### How It Works

1. Click the **GitHub** button in the sidebar to start the OAuth flow
2. Authorize the app on GitHub — you'll be redirected back to the dashboard
3. Select a repository to link tasks to
4. On any task card, click the GitHub icon to push it as an issue
5. Linked tasks show a badge with the issue number — click it to open the issue on GitHub
6. When you change a task's status in the dashboard, the linked GitHub issue is updated automatically

## API Endpoints

| Method | Endpoint                          | Description                      |
| ------ | --------------------------------- | -------------------------------- |
| GET    | `/api/stats`                      | Dashboard statistics             |
| GET    | `/api/projects`                   | List all projects                |
| POST   | `/api/projects`                   | Create a project                 |
| DELETE | `/api/projects/<id>`              | Delete a project                 |
| GET    | `/api/tasks?project_id=N`         | List tasks (filter)              |
| POST   | `/api/tasks`                      | Create a task                    |
| PATCH  | `/api/tasks/<id>`                 | Update a task                    |
| DELETE | `/api/tasks/<id>`                 | Delete a task                    |
| GET    | `/api/github/auth`                | Start GitHub OAuth flow          |
| GET    | `/api/github/callback`            | Handle OAuth callback            |
| GET    | `/api/github/status`              | Check GitHub connection status   |
| POST   | `/api/github/disconnect`          | Disconnect GitHub account        |
| GET    | `/api/github/repos`               | List user's GitHub repositories  |
| POST   | `/api/github/repo`                | Select repository for issues     |
| POST   | `/api/tasks/<id>/push-to-github`  | Push task as GitHub issue        |
| POST   | `/api/tasks/<id>/sync-github`     | Sync task status from GitHub     |

## Tech Stack

- **Backend:** Flask, Flask-SQLAlchemy, Flask-CORS, SQLite
- **Frontend:** React 18, Vite 5, vanilla CSS
- **Fonts:** Inter (Google Fonts)
