import type { StepName, StepStatus } from "../types";

const WORKFLOW_STEPS: readonly StepName[] = [
  "Reference",
  "STT",
  "Analysis",
  "Candidates",
  "Script",
  "Production",
  "Render"
];

interface ProjectWorkflowProps {
  readonly currentStep: StepName;
  readonly stepStatuses: readonly StepStatus[];
  readonly hasAudio?: boolean;
  readonly isAudioBusy?: boolean;
  readonly isSttBusy?: boolean;
  readonly isAnalysisBusy?: boolean;
  readonly hasAnalysis?: boolean;
  readonly hasSelectedReference?: boolean;
}

interface WorkflowItem {
  id: string;
  name: string;
  state: "waiting" | "running" | "succeeded" | "failed";
  message: string;
  isActive: boolean;
}

function stateLabel(state: string): string {
  return state.charAt(0).toUpperCase() + state.slice(1);
}

export function ProjectWorkflow({
  currentStep,
  stepStatuses,
  hasAudio = false,
  isAudioBusy = false,
  isSttBusy = false,
  isAnalysisBusy = false,
  hasAnalysis = false,
  hasSelectedReference = false
}: ProjectWorkflowProps) {
  const statusesByName = new Map(stepStatuses.map((status) => [status.name, status]));

  const referenceStatus = statusesByName.get("Reference");
  const sttStatus = statusesByName.get("STT");
  const analysisStatus = statusesByName.get("Analysis");

  // Determine current effective active step
  let effectiveStepName = currentStep as string;
  if (currentStep === "STT") {
    if (!hasAudio) {
      effectiveStepName = "Extract Audio";
    }
  }

  // Build the pipeline items
  const items: WorkflowItem[] = [
    {
      id: "reference",
      name: "Reference",
      state: referenceStatus?.state ?? "waiting",
      message: referenceStatus?.message || (referenceStatus?.state === "succeeded" ? "Reference selected." : "Select a reference."),
      isActive: currentStep === "Reference"
    },
    {
      id: "extract-audio",
      name: "Extract Audio",
      state: isAudioBusy
        ? "running"
        : hasAudio
        ? "succeeded"
        : hasSelectedReference
        ? "waiting"
        : "waiting",
      message: isAudioBusy
        ? "Extracting reference audio..."
        : hasAudio
        ? "Reference audio extracted."
        : hasSelectedReference
        ? "Ready to extract audio."
        : "Waiting for reference selection.",
      isActive: effectiveStepName === "Extract Audio"
    },
    {
      id: "stt",
      name: "STT",
      state: isSttBusy || sttStatus?.state === "running"
        ? "running"
        : sttStatus?.state === "succeeded"
        ? "succeeded"
        : "waiting",
      message: isSttBusy
        ? "Running OpenAI STT..."
        : sttStatus?.message || (
          sttStatus?.state === "succeeded"
            ? "Reference STT complete."
            : hasAudio
            ? "Ready for STT."
            : "Waiting for audio extraction."
        ),
      isActive: effectiveStepName === "STT"
    },
    {
      id: "analysis",
      name: "Analysis",
      state: isAnalysisBusy
        ? "running"
        : hasAnalysis || analysisStatus?.state === "succeeded"
        ? "succeeded"
        : analysisStatus?.state === "running" && analysisStatus?.message !== "Reference script is ready for analysis."
        ? "running"
        : "waiting",
      message: isAnalysisBusy
        ? "Analyzing reference script..."
        : hasAnalysis || analysisStatus?.state === "succeeded"
        ? (analysisStatus?.message || "Reference analysis complete.")
        : (analysisStatus?.message || "Reference script is ready for analysis."),
      isActive: effectiveStepName === "Analysis"
    },
    ...(["Candidates", "Script", "Production", "Render"] as const).map((step) => {
      const status = statusesByName.get(step);
      let effectiveState = (status?.state ?? "waiting") as WorkflowItem["state"];
      if (step === "Candidates" && status?.message?.startsWith("Ready to generate")) {
        effectiveState = "waiting";
      }
      return {
        id: step.toLowerCase(),
        name: step,
        state: effectiveState,
        message: status?.message || "",
        isActive: currentStep === step
      };
    })
  ];

  return (
    <section className="panel workflow-panel" aria-labelledby="workflow-title">
      <div className="section-header">
        <div>
          <p className="eyebrow">Workflow</p>
          <h2 id="workflow-title">Production pipeline</h2>
        </div>
        <span className="current-step">현재 단계: {effectiveStepName}</span>
      </div>

      <ol className="workflow-list">
        {items.map((item, index) => {
          const label = stateLabel(item.state);
          return (
            <li
              className={[
                "workflow-step",
                item.isActive ? "active" : "",
                `workflow-step--${item.state}`
              ]
                .filter(Boolean)
                .join(" ")}
              key={item.id}
            >
              <span className="step-index">{index + 1}</span>
              <span className={item.isActive ? "step-main active" : "step-main"}>
                <strong aria-current={item.isActive ? "step" : undefined} className={item.isActive ? "active" : undefined}>
                  {item.name}
                </strong>
                <span>{item.message || label}</span>
              </span>
              <span className={`state-pill state-pill--${item.state}`}>{label}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
