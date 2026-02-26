interface PipelineStepperProps {
  currentPhase: number;
}

const PHASES = ['1. Upload', '2. Authenticité', '3. Prix', '4. Post', '5. Smart Contract', '6. Enchère'];

export function PipelineStepper({ currentPhase }: PipelineStepperProps) {
  return (
    <div className="pipeline-stepper">
      {PHASES.map((label, i) => {
        const phase = i + 1;
        const done = currentPhase > phase;
        const active = currentPhase === phase;
        return (
          <div key={phase} className={`step ${done ? 'done' : ''} ${active ? 'active' : ''}`}>
            <span className="step-num">{done ? '✓' : phase}</span>
            <span className="step-label">{label}</span>
          </div>
        );
      })}
    </div>
  );
}
