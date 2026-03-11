export default function Sidebar({
  projects,
  selectedProject,
  onSelect,
  onNewProject,
  onDeleteProject,
  theme,
  onToggleTheme,
  onOpenGitHub,
  githubStatus,
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
          </svg>
        </div>
        <span className="brand-text">Dashboard</span>
        <button
          className="theme-toggle"
          onClick={onToggleTheme}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        >
          {theme === "dark" ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
            </svg>
          )}
        </button>
      </div>

      <nav className="sidebar-nav">
        <button
          className={`nav-item ${selectedProject === null ? "active" : ""}`}
          onClick={() => onSelect(null)}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
            <polyline points="9 22 9 12 15 12 15 22" />
          </svg>
          All Projects
        </button>

        <div className="nav-section-label">Projects</div>

        {projects.map((p) => (
          <div key={p.id} className="nav-project-row">
            <button
              className={`nav-item ${selectedProject === p.id ? "active" : ""}`}
              onClick={() => onSelect(p.id)}
            >
              <span
                className="project-dot"
                style={{ backgroundColor: p.color }}
              />
              <span className="nav-item-text">{p.name}</span>
              <span className="task-badge">
                {p.completed_count}/{p.task_count}
              </span>
            </button>
            <button
              className="nav-delete"
              title="Delete project"
              onClick={(e) => {
                e.stopPropagation();
                if (window.confirm(`Delete "${p.name}" and all its tasks?`)) {
                  onDeleteProject(p.id);
                }
              }}
            >
              &times;
            </button>
          </div>
        ))}
      </nav>

      <div className="sidebar-bottom">
        <button className="btn btn-ghost sidebar-add" onClick={onNewProject}>
          + New Project
        </button>
        <button
          className={`nav-item gh-nav-item ${githubStatus?.connected ? "gh-connected" : ""}`}
          onClick={onOpenGitHub}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
          </svg>
          <span className="nav-item-text">
            {githubStatus?.connected ? githubStatus.username : "Connect GitHub"}
          </span>
          {githubStatus?.connected && (
            <span className="gh-status-dot" />
          )}
        </button>
      </div>
    </aside>
  );
}
