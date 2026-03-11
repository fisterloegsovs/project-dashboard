import { useState } from "react";

const COLORS = ["#6366f1", "#ec4899", "#14b8a6", "#f59e0b", "#3b82f6", "#ef4444", "#8b5cf6", "#06b6d4"];

export default function ProjectModal({ onSave, onClose }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState(COLORS[0]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSave({ name: name.trim(), description, color });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>New Project</h2>
          <button className="modal-close" onClick={onClose}>
            &times;
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <label className="field">
            <span>Name</span>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Project name"
            />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description..."
              rows={2}
            />
          </label>
          <div className="field">
            <span>Color</span>
            <div className="color-picker">
              {COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  className={`color-swatch ${c === color ? "selected" : ""}`}
                  style={{ backgroundColor: c }}
                  onClick={() => setColor(c)}
                />
              ))}
            </div>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              Create Project
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
