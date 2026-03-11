const API = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || res.statusText);
  }
  // Handle empty responses (e.g. 204 No Content)
  const text = await res.text();
  return text ? JSON.parse(text) : {};
}

export const api = {
  // Stats
  getStats: () => request("/stats"),

  // Projects
  getProjects: () => request("/projects"),
  createProject: (data) =>
    request("/projects", { method: "POST", body: JSON.stringify(data) }),
  deleteProject: (id) =>
    request(`/projects/${id}`, { method: "DELETE" }),

  // Tasks
  getTasks: (projectId) =>
    request(`/tasks${projectId ? `?project_id=${projectId}` : ""}`),
  createTask: (data) =>
    request("/tasks", { method: "POST", body: JSON.stringify(data) }),
  updateTask: (id, data) =>
    request(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteTask: (id) =>
    request(`/tasks/${id}`, { method: "DELETE" }),

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
