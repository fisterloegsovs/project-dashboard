import { useState } from "react";

export default function TaskModal({ projects, defaultProject, onSave, onClose }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [projectId, setProjectId] = useState(defaultProject || projects[0]?.id || "");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!title.trim() || !projectId) return;
    onSave({ title: title.trim(), description, priority, project_id: projectId });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>New Task</h2>
          <button className="modal-close" onClick={onClose}>
            &times;
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <label className="field">
            <span>Title</span>
            <input
              autoFocus
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="What needs to be done?"
            />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional details..."
              rows={3}
            />
          </label>
          <div className="field-row">
            <label className="field">
              <span>Project</span>
              <select
                value={projectId}
                onChange={(e) => setProjectId(Number(e.target.value))}
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Priority</span>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              Create Task
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
