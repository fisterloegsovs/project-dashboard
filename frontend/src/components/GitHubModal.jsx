import { useState, useEffect } from "react";
import { api } from "../api";

export default function GitHubModal({ onClose, onStatusChange }) {
  const [status, setStatus] = useState(null);
  const [repos, setRepos] = useState([]);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [selectedRepo, setSelectedRepo] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getGitHubStatus().then(setStatus).catch(() => setStatus({ connected: false }));
  }, []);

  useEffect(() => {
    if (status?.connected) {
      setSelectedRepo(status.selected_repo || "");
      setLoadingRepos(true);
      api
        .getGitHubRepos()
        .then(setRepos)
        .catch(() => setError("Failed to load repositories"))
        .finally(() => setLoadingRepos(false));
    }
  }, [status?.connected]);

  const handleConnect = () => {
    // Redirect to backend OAuth endpoint — it will redirect to GitHub
    window.location.href = "/api/github/auth";
  };

  const handleDisconnect = async () => {
    await api.disconnectGitHub();
    setStatus({ connected: false });
    setRepos([]);
    setSelectedRepo("");
    onStatusChange?.();
  };

  const handleSaveRepo = async () => {
    if (!selectedRepo) return;
    setSaving(true);
    setError("");
    try {
      const updated = await api.setGitHubRepo(selectedRepo);
      setStatus(updated);
      onStatusChange?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (!status) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal" onClick={(e) => e.stopPropagation()}>
          <div className="loading-screen" style={{ height: "200px" }}>
            <div className="loading-spinner" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>GitHub Integration</h2>
          <button className="modal-close" onClick={onClose}>
            &times;
          </button>
        </div>

        {!status.connected ? (
          <div className="gh-connect-section">
            <div className="gh-connect-info">
              <svg className="gh-logo" width="40" height="40" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              <p>Connect your GitHub account to push tasks as issues and keep them in sync.</p>
            </div>
            <button className="btn btn-github" onClick={handleConnect}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              Connect with GitHub
            </button>
          </div>
        ) : (
          <div className="gh-connected-section">
            <div className="gh-user-row">
              {status.avatar && (
                <img
                  className="gh-avatar"
                  src={status.avatar}
                  alt={status.username}
                />
              )}
              <div className="gh-user-info">
                <span className="gh-username">{status.username}</span>
                <span className="gh-connected-label">Connected</span>
              </div>
              <button
                className="btn btn-sm btn-ghost"
                onClick={handleDisconnect}
              >
                Disconnect
              </button>
            </div>

            <div className="field" style={{ marginTop: 16 }}>
              <span>Repository</span>
              {loadingRepos ? (
                <div className="gh-loading-repos">
                  <div className="loading-spinner" style={{ width: 20, height: 20, borderWidth: 2 }} />
                  <span>Loading repositories...</span>
                </div>
              ) : (
                <select
                  value={selectedRepo}
                  onChange={(e) => setSelectedRepo(e.target.value)}
                >
                  <option value="">Select a repository...</option>
                  {repos.map((r) => (
                    <option key={r.full_name} value={r.full_name}>
                      {r.full_name} {r.private ? "(private)" : ""}
                    </option>
                  ))}
                </select>
              )}
              <span className="gh-repo-hint">
                Issues will be created in this repository when you push tasks.
              </span>
            </div>

            {error && <p className="gh-error">{error}</p>}

            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={onClose}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                disabled={!selectedRepo || saving || selectedRepo === status.selected_repo}
                onClick={handleSaveRepo}
              >
                {saving ? "Saving..." : "Save Repository"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
