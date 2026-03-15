import { useState, useEffect, useCallback } from "react";
import { api } from "./api";
import { useAuth } from "./context/AuthContext";
import AuthPage from "./components/AuthPage";
import Sidebar from "./components/Sidebar";
import StatsBar from "./components/StatsBar";
import ProjectBoard from "./components/ProjectBoard";
import TaskModal from "./components/TaskModal";
import ProjectModal from "./components/ProjectModal";
import GitHubModal from "./components/GitHubModal";
import TeamModal from "./components/TeamModal";
import VideoCallModal from "./components/VideoCallModal";

export default function App() {
  const { user, loading: authLoading, canModify } = useAuth();

  const [projects, setProjects] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedProject, setSelectedProject] = useState(null);
  const [selectedTeam, setSelectedTeam] = useState(null);
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [showProjectModal, setShowProjectModal] = useState(false);
  const [showGitHubModal, setShowGitHubModal] = useState(false);
  const [showTeamModal, setShowTeamModal] = useState(false);
  const [editingTeam, setEditingTeam] = useState(null);
  const [githubStatus, setGithubStatus] = useState(null);
  const [activeCalls, setActiveCalls] = useState([]);
  const [activeCall, setActiveCall] = useState(null);
  const [loading, setLoading] = useState(true);
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "dark");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));

  // Handle GitHub OAuth callback
  useEffect(() => {
    const path = window.location.pathname;
    const params = new URLSearchParams(window.location.search);
    if (path === "/github/callback" && params.get("code")) {
      fetch(`/api/github/callback?code=${params.get("code")}&state=${params.get("state") || ""}`)
        .then((r) => {
          if (!r.ok) throw new Error(`GitHub callback failed: ${r.status}`);
          return r.json();
        })
        .then(() => {
          window.history.replaceState({}, "", "/");
          refreshGitHubStatus();
          setShowGitHubModal(true);
        })
        .catch((e) => {
          console.error("GitHub callback error:", e);
          window.history.replaceState({}, "", "/");
        });
    }
  }, []);

  const refreshGitHubStatus = useCallback(async () => {
    try {
      const s = await api.getGitHubStatus();
      setGithubStatus(s);
    } catch {
      setGithubStatus({ connected: false });
    }
  }, []);

  const refreshCalls = useCallback(async () => {
    try {
      const calls = await api.getCalls(selectedTeam);
      setActiveCalls(calls);
    } catch {
      setActiveCalls([]);
    }
  }, [selectedTeam]);

  const refresh = useCallback(async () => {
    try {
      const [p, t, s] = await Promise.all([
        api.getProjects(selectedTeam),
        api.getTasks(selectedProject, selectedTeam),
        api.getStats(selectedTeam),
      ]);
      setProjects(p);
      setTasks(t);
      setStats(s);
    } catch (e) {
      console.error("Failed to fetch data:", e);
    } finally {
      setLoading(false);
    }
  }, [selectedProject, selectedTeam]);

  useEffect(() => {
    if (user) {
      refresh();
      refreshGitHubStatus();
      refreshCalls();
    }
  }, [user, refresh, refreshGitHubStatus, refreshCalls]);

  // Auto-select first team
  useEffect(() => {
    if (user?.teams?.length > 0 && !selectedTeam) {
      setSelectedTeam(user.teams[0].id);
    }
  }, [user?.teams, selectedTeam]);

  const handleSelectProject = (id) => {
    setSelectedProject(id === selectedProject ? null : id);
  };

  const handleSelectTeam = (id) => {
    setSelectedTeam(id);
    setSelectedProject(null);
  };

  const handleTaskCreate = async (data) => {
    try {
      await api.createTask(data);
      setShowTaskModal(false);
      refresh();
    } catch (e) {
      console.error("Failed to create task:", e);
      alert(`Failed to create task: ${e.message}`);
    }
  };

  const handleTaskUpdate = async (id, data) => {
    try {
      await api.updateTask(id, data);
      refresh();
    } catch (e) {
      console.error("Failed to update task:", e);
    }
  };

  const handleTaskDelete = async (id) => {
    try {
      await api.deleteTask(id);
      refresh();
    } catch (e) {
      console.error("Failed to delete task:", e);
    }
  };

  const handleProjectCreate = async (data) => {
    try {
      await api.createProject({ ...data, team_id: selectedTeam });
      setShowProjectModal(false);
      refresh();
    } catch (e) {
      console.error("Failed to create project:", e);
      alert(`Failed to create project: ${e.message}`);
    }
  };

  const handleProjectDelete = async (id) => {
    try {
      await api.deleteProject(id);
      if (selectedProject === id) setSelectedProject(null);
      refresh();
    } catch (e) {
      console.error("Failed to delete project:", e);
    }
  };

  const handlePushToGitHub = async (taskId) => {
    try {
      await api.pushTaskToGitHub(taskId);
      refresh();
    } catch (e) {
      alert(`Failed to push to GitHub: ${e.message}`);
    }
  };

  const handleStartCall = async () => {
    try {
      const call = await api.createCall({ team_id: selectedTeam });
      setActiveCall(call);
      refreshCalls();
    } catch (e) {
      alert(`Failed to start call: ${e.message}`);
    }
  };

  const handleJoinCall = (call) => {
    setActiveCall(call);
  };

  const handleCloseCall = () => {
    setActiveCall(null);
    refreshCalls();
  };

  const handleOpenTeamModal = (team) => {
    setEditingTeam(team || null);
    setShowTeamModal(true);
  };

  // Show auth page if not logged in
  if (authLoading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner" />
        <p>Loading...</p>
      </div>
    );
  }

  if (!user) {
    return <AuthPage />;
  }

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner" />
        <p>Loading dashboard...</p>
      </div>
    );
  }

  const currentTeamRole = user.teams?.find((t) => t.id === selectedTeam)?.role;
  const userCanModify = canModify(selectedTeam);

  return (
    <div className="app">
      <Sidebar
        projects={projects}
        selectedProject={selectedProject}
        onSelect={handleSelectProject}
        onNewProject={() => setShowProjectModal(true)}
        onDeleteProject={handleProjectDelete}
        theme={theme}
        onToggleTheme={toggleTheme}
        onOpenGitHub={() => setShowGitHubModal(true)}
        githubStatus={githubStatus}
        teams={user.teams || []}
        selectedTeam={selectedTeam}
        onSelectTeam={handleSelectTeam}
        onOpenTeamModal={handleOpenTeamModal}
        onStartCall={handleStartCall}
        activeCalls={activeCalls}
        onJoinCall={handleJoinCall}
      />
      <main className="main">
        <header className="main-header">
          <div>
            <h1>
              {selectedProject
                ? projects.find((p) => p.id === selectedProject)?.name ||
                  "Project"
                : "All Projects"}
            </h1>
            <p className="subtitle">
              {selectedProject
                ? projects.find((p) => p.id === selectedProject)?.description
                : "Overview of all your work"}
              {currentTeamRole && (
                <span className="header-role-badge">{currentTeamRole}</span>
              )}
            </p>
          </div>
          {userCanModify && (
            <button
              className="btn btn-primary"
              onClick={() => setShowTaskModal(true)}
            >
              <span className="btn-icon">+</span> New Task
            </button>
          )}
        </header>

        {stats && <StatsBar stats={stats} />}

        <ProjectBoard
          tasks={tasks}
          projects={projects}
          onUpdate={handleTaskUpdate}
          onDelete={handleTaskDelete}
          onPushToGitHub={handlePushToGitHub}
          githubConnected={githubStatus?.connected && !!githubStatus?.selected_repo}
          canModify={userCanModify}
        />
      </main>

      {showTaskModal && (
        <TaskModal
          projects={projects}
          defaultProject={selectedProject}
          teamId={selectedTeam}
          onSave={handleTaskCreate}
          onClose={() => setShowTaskModal(false)}
        />
      )}

      {showProjectModal && (
        <ProjectModal
          onSave={handleProjectCreate}
          onClose={() => setShowProjectModal(false)}
        />
      )}

      {showGitHubModal && (
        <GitHubModal
          onClose={() => setShowGitHubModal(false)}
          onStatusChange={refreshGitHubStatus}
        />
      )}

      {showTeamModal && (
        <TeamModal
          team={editingTeam}
          onClose={() => {
            setShowTeamModal(false);
            setEditingTeam(null);
          }}
          onSaved={refresh}
        />
      )}

      {activeCall && (
        <VideoCallModal
          call={activeCall}
          onClose={handleCloseCall}
        />
      )}
    </div>
  );
}
