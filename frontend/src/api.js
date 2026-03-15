const API = "/api";

function getToken() {
  return localStorage.getItem("token");
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API}${path}`, {
    headers,
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || res.statusText);
  }
  const text = await res.text();
  return text ? JSON.parse(text) : {};
}

export const api = {
  // Auth
  register: (data) =>
    request("/auth/register", { method: "POST", body: JSON.stringify(data) }),
  login: (data) =>
    request("/auth/login", { method: "POST", body: JSON.stringify(data) }),
  getMe: () => request("/auth/me"),

  // Stats
  getStats: (teamId) =>
    request(`/stats${teamId ? `?team_id=${teamId}` : ""}`),

  // Projects
  getProjects: (teamId) =>
    request(`/projects${teamId ? `?team_id=${teamId}` : ""}`),
  createProject: (data) =>
    request("/projects", { method: "POST", body: JSON.stringify(data) }),
  deleteProject: (id) =>
    request(`/projects/${id}`, { method: "DELETE" }),

  // Tasks
  getTasks: (projectId, teamId) => {
    const params = new URLSearchParams();
    if (projectId) params.set("project_id", projectId);
    if (teamId) params.set("team_id", teamId);
    const qs = params.toString();
    return request(`/tasks${qs ? `?${qs}` : ""}`);
  },
  createTask: (data) =>
    request("/tasks", { method: "POST", body: JSON.stringify(data) }),
  updateTask: (id, data) =>
    request(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteTask: (id) =>
    request(`/tasks/${id}`, { method: "DELETE" }),

  // Teams
  getTeams: () => request("/teams"),
  createTeam: (data) =>
    request("/teams", { method: "POST", body: JSON.stringify(data) }),
  getTeam: (id) => request(`/teams/${id}`),
  updateTeam: (id, data) =>
    request(`/teams/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteTeam: (id) =>
    request(`/teams/${id}`, { method: "DELETE" }),
  addTeamMember: (teamId, data) =>
    request(`/teams/${teamId}/members`, { method: "POST", body: JSON.stringify(data) }),
  updateTeamMember: (teamId, userId, data) =>
    request(`/teams/${teamId}/members/${userId}`, { method: "PATCH", body: JSON.stringify(data) }),
  removeTeamMember: (teamId, userId) =>
    request(`/teams/${teamId}/members/${userId}`, { method: "DELETE" }),

  // Users
  getUsers: (q, teamId) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (teamId) params.set("team_id", teamId);
    const qs = params.toString();
    return request(`/users${qs ? `?${qs}` : ""}`);
  },

  // Video Calls
  getCalls: (teamId) =>
    request(`/calls${teamId ? `?team_id=${teamId}` : ""}`),
  createCall: (data) =>
    request("/calls", { method: "POST", body: JSON.stringify(data) }),
  endCall: (id) =>
    request(`/calls/${id}/end`, { method: "POST" }),

  // GitHub
  getGitHubStatus: () => request("/github/status"),
  disconnectGitHub: () =>
    request("/github/disconnect", { method: "POST" }),
  getGitHubRepos: () => request("/github/repos"),
  setGitHubRepo: (repo) =>
    request("/github/repo", { method: "PUT", body: JSON.stringify({ repo }) }),
  pushTaskToGitHub: (taskId) =>
    request(`/tasks/${taskId}/push-to-github`, { method: "POST" }),
  syncTaskFromGitHub: (taskId) =>
    request(`/tasks/${taskId}/sync-github`, { method: "POST" }),
};
