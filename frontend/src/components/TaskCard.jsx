import { useState } from "react";

const PRIORITY_COLORS = {
  high: "#ef4444",
  medium: "#f59e0b",
  low: "#6b7280",
};

const NEXT_STATUS = {
  todo: "in_progress",
  in_progress: "completed",
  completed: "todo",
};

const STATUS_LABELS = {
  todo: "Start",
  in_progress: "Complete",
  completed: "Reopen",
};

export default function TaskCard({ task, project, onUpdate, onDelete, onPushToGitHub, githubConnected, canModify }) {
  const [pushing, setPushing] = useState(false);

  const handlePush = async () => {
    setPushing(true);
    try {
      await onPushToGitHub(task.id);
    } finally {
      setPushing(false);
    }
  };

  return (
    <div className="task-card">
      <div className="task-card-top">
        <div className="task-card-badges">
          <span
            className="priority-badge"
            style={{ backgroundColor: PRIORITY_COLORS[task.priority] }}
          >
            {task.priority}
          </span>
          {task.github_issue_url && (
            <a
              className="gh-issue-badge"
              href={task.github_issue_url}
              target="_blank"
              rel="noopener noreferrer"
              title={`GitHub issue #${task.github_issue_number}`}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              #{task.github_issue_number}
            </a>
          )}
        </div>
        {canModify && (
          <button
            className="task-delete"
            title="Delete task"
            onClick={() => onDelete(task.id)}
          >
            &times;
          </button>
        )}
      </div>
      <h4 className="task-title">{task.title}</h4>
      {task.description && (
        <p className="task-desc">{task.description}</p>
      )}
      <div className="task-card-bottom">
        <div className="task-card-meta">
          {project && (
            <span className="task-project">
              <span
                className="project-dot-sm"
                style={{ backgroundColor: project.color }}
              />
              {project.name}
            </span>
          )}
          {task.assignee && (
            <span className="task-assignee" title={`Assigned to ${task.assignee.display_name}`}>
              <span
                className="assignee-dot"
                style={{ backgroundColor: task.assignee.avatar_color }}
              >
                {(task.assignee.display_name || task.assignee.username)[0].toUpperCase()}
              </span>
              {task.assignee.display_name}
            </span>
          )}
        </div>
        <div className="task-card-actions">
          {githubConnected && !task.github_issue_url && canModify && (
            <button
              className="btn btn-sm btn-gh-push"
              onClick={handlePush}
              disabled={pushing}
              title="Push to GitHub as issue"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              {pushing ? "..." : "Push"}
            </button>
          )}
          {canModify && (
            <button
              className="btn btn-sm"
              onClick={() =>
                onUpdate(task.id, { status: NEXT_STATUS[task.status] })
              }
            >
              {STATUS_LABELS[task.status]}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
