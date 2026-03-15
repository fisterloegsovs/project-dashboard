import TaskCard from "./TaskCard";

const COLUMNS = [
  { key: "todo", label: "To Do", color: "#6366f1" },
  { key: "in_progress", label: "In Progress", color: "#f59e0b" },
  { key: "completed", label: "Completed", color: "#10b981" },
];

export default function ProjectBoard({ tasks, projects, onUpdate, onDelete, onPushToGitHub, githubConnected, canModify }) {
  const projectMap = Object.fromEntries(projects.map((p) => [p.id, p]));

  return (
    <div className="board">
      {COLUMNS.map((col) => {
        const colTasks = tasks.filter((t) => t.status === col.key);
        return (
          <div key={col.key} className="board-column">
            <div className="column-header">
              <span
                className="column-dot"
                style={{ backgroundColor: col.color }}
              />
              <h3>{col.label}</h3>
              <span className="column-count">{colTasks.length}</span>
            </div>
            <div className="column-body">
              {colTasks.length === 0 && (
                <p className="empty-col">No tasks here</p>
              )}
              {colTasks.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  project={projectMap[task.project_id]}
                  onUpdate={onUpdate}
                  onDelete={onDelete}
                  onPushToGitHub={onPushToGitHub}
                  githubConnected={githubConnected}
                  canModify={canModify}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
