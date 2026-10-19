import type { Project } from "../types";

interface ProjectDashboardProps {
  readonly projects: readonly Project[];
  readonly selectedProjectId: string | null;
  readonly onCreateProject: () => void;
  readonly onSelectProject: (project: Project) => void;
}

export function ProjectDashboard({
  projects,
  selectedProjectId,
  onCreateProject,
  onSelectProject
}: ProjectDashboardProps) {
  return (
    <section className="dashboard" aria-labelledby="projects-title">
      <header className="project-hero project-hero--compact">
        <div>
          <p className="eyebrow">Local shorts production</p>
          <h1 id="projects-title">Projects</h1>
          <p className="muted">Manage local Phase 1 project folders.</p>
        </div>
        <button className="primary-button" onClick={onCreateProject} type="button">
          New Project
        </button>
      </header>

      <div className="project-list" role="list">
        {projects.length === 0 ? (
          <p className="empty-state">No projects yet.</p>
        ) : (
          projects.map((project) => (
            <button
              className="project-list-item"
              key={project.project_id}
              aria-current={project.project_id === selectedProjectId ? "page" : undefined}
              onClick={() => onSelectProject(project)}
              type="button"
            >
              <strong>{project.display_name}</strong>
              <span>{project.current_step}</span>
            </button>
          ))
        )}
      </div>
    </section>
  );
}
