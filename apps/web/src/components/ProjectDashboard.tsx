import type { Project } from "../types";

interface ProjectDashboardProps {
  readonly projects: readonly Project[];
  readonly selectedProjectId: string | null;
  readonly onCreateProject: () => void;
  readonly onSelectProject: (project: Project) => void;
  readonly onDeleteProject?: (projectId: string) => void;
}

export function ProjectDashboard({
  projects,
  selectedProjectId,
  onCreateProject,
  onSelectProject,
  onDeleteProject
}: ProjectDashboardProps) {
  return (
    <section className="dashboard" aria-label="Projects">
      <header className="project-hero project-hero--compact">
        <button className="primary-button" onClick={onCreateProject} type="button">
          + New Project
        </button>
      </header>

      <div className="project-list" role="list">
        {projects.length === 0 ? (
          <p className="empty-state">No projects yet.</p>
        ) : (
          projects.map((project) => (
            <div className="project-list-row" key={project.project_id}>
              <button
                className="project-list-item"
                aria-current={project.project_id === selectedProjectId ? "page" : undefined}
                onClick={() => onSelectProject(project)}
                type="button"
              >
                <strong>{project.display_name}</strong>
                <span>{project.current_step}</span>
              </button>
              {onDeleteProject ? (
                <button
                  className="project-delete-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteProject(project.project_id);
                  }}
                  type="button"
                  title="프로젝트 삭제"
                  aria-label={`${project.display_name} 삭제`}
                >
                  🗑️
                </button>
              ) : null}
            </div>
          ))
        )}
      </div>
    </section>
  );
}
