import { useState, useEffect } from "react";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";

const COLORS = ["#6366f1", "#ec4899", "#14b8a6", "#f59e0b", "#3b82f6", "#ef4444", "#8b5cf6", "#06b6d4"];
const ROLE_LABELS = { admin: "Admin", member: "Member", viewer: "Viewer" };

export default function TeamModal({ team, onClose, onSaved }) {
  const { user, canAdmin, refreshUser } = useAuth();
  const isEditing = !!team;
  const isAdmin = isEditing ? canAdmin(team.id) : true;

  // Create form
  const [name, setName] = useState(team?.name || "");
  const [description, setDescription] = useState(team?.description || "");
  const [color, setColor] = useState(team?.color || COLORS[0]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Members (only when editing)
  const [members, setMembers] = useState([]);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newRole, setNewRole] = useState("member");
  const [addError, setAddError] = useState("");

  useEffect(() => {
    if (isEditing) {
      setLoadingMembers(true);
      api
        .getTeam(team.id)
        .then((t) => setMembers(t.members || []))
        .catch(() => {})
        .finally(() => setLoadingMembers(false));
    }
  }, [isEditing, team?.id]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError("");
    try {
      if (isEditing) {
        await api.updateTeam(team.id, { name: name.trim(), description, color });
      } else {
        await api.createTeam({ name: name.trim(), description, color });
      }
      await refreshUser();
      onSaved?.();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleAddMember = async () => {
    if (!newUsername.trim()) return;
    setAddError("");
    try {
      await api.addTeamMember(team.id, { username: newUsername.trim(), role: newRole });
      // Refresh members
      const t = await api.getTeam(team.id);
      setMembers(t.members || []);
      setNewUsername("");
    } catch (err) {
      setAddError(err.message);
    }
  };

  const handleRoleChange = async (userId, role) => {
    try {
      await api.updateTeamMember(team.id, userId, { role });
      const t = await api.getTeam(team.id);
      setMembers(t.members || []);
    } catch (err) {
      setAddError(err.message);
    }
  };

  const handleRemoveMember = async (userId) => {
    if (!window.confirm("Remove this member from the team?")) return;
    try {
      await api.removeTeamMember(team.id, userId);
      const t = await api.getTeam(team.id);
      setMembers(t.members || []);
      await refreshUser();
    } catch (err) {
      setAddError(err.message);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete team "${team.name}"? This cannot be undone.`)) return;
    try {
      await api.deleteTeam(team.id);
      await refreshUser();
      onSaved?.();
      onClose();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{isEditing ? "Team Settings" : "New Team"}</h2>
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
              placeholder="Team name"
              disabled={isEditing && !isAdmin}
            />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this team work on?"
              rows={2}
              disabled={isEditing && !isAdmin}
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
                  disabled={isEditing && !isAdmin}
                />
              ))}
            </div>
          </div>

          {error && <p className="auth-error">{error}</p>}

          {(!isEditing || isAdmin) && (
            <div className="modal-actions">
              {isEditing && isAdmin && (
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={handleDelete}
                >
                  Delete Team
                </button>
              )}
              <div style={{ flex: 1 }} />
              <button type="button" className="btn btn-ghost" onClick={onClose}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? "Saving..." : isEditing ? "Save" : "Create Team"}
              </button>
            </div>
          )}
        </form>

        {/* Members section (only when editing) */}
        {isEditing && (
          <div className="team-members-section">
            <h3 className="team-members-title">Members</h3>

            {loadingMembers ? (
              <div className="gh-loading-repos">
                <div className="loading-spinner" style={{ width: 20, height: 20, borderWidth: 2 }} />
                <span>Loading members...</span>
              </div>
            ) : (
              <div className="team-members-list">
                {members.map((m) => (
                  <div key={m.id} className="team-member-row">
                    <div
                      className="team-member-avatar"
                      style={{ backgroundColor: m.user?.avatar_color || "#6366f1" }}
                    >
                      {(m.user?.display_name || m.user?.username || "?")[0].toUpperCase()}
                    </div>
                    <div className="team-member-info">
                      <span className="team-member-name">
                        {m.user?.display_name || m.user?.username}
                      </span>
                      <span className="team-member-username">@{m.user?.username}</span>
                    </div>
                    {isAdmin && m.user_id !== user.id ? (
                      <>
                        <select
                          className="team-role-select"
                          value={m.role}
                          onChange={(e) => handleRoleChange(m.user_id, e.target.value)}
                        >
                          <option value="admin">Admin</option>
                          <option value="member">Member</option>
                          <option value="viewer">Viewer</option>
                        </select>
                        <button
                          className="btn btn-sm btn-ghost"
                          onClick={() => handleRemoveMember(m.user_id)}
                          title="Remove member"
                        >
                          &times;
                        </button>
                      </>
                    ) : (
                      <span className="team-role-badge">{ROLE_LABELS[m.role]}</span>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Add member form */}
            {isAdmin && (
              <div className="team-add-member">
                <input
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  placeholder="Username to add..."
                  className="team-add-input"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddMember();
                    }
                  }}
                />
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value)}
                  className="team-role-select"
                >
                  <option value="member">Member</option>
                  <option value="viewer">Viewer</option>
                  <option value="admin">Admin</option>
                </select>
                <button
                  type="button"
                  className="btn btn-sm btn-primary"
                  onClick={handleAddMember}
                >
                  Add
                </button>
              </div>
            )}
            {addError && <p className="auth-error" style={{ marginTop: 8 }}>{addError}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
