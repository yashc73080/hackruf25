'use client';

import { useState } from 'react';
import ProjectPlanningChat from '@/components/ProjectPlanningChat';
import TeamInputForm from '@/components/TeamInputForm';

const PHASES = {
  PLANNING: 'planning',
  TEAM_INPUT: 'team-input',
  // RESULTS: 'matching-results', 
};

export default function Home() {
  const [currentPhase, setCurrentPhase] = useState(PHASES.PLANNING);
  
  // This function is passed to the chat component to advance the project.
  const handleDonePlanning = () => {
    setCurrentPhase(PHASES.TEAM_INPUT);
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 sm:p-8 md:p-12 bg-background">
      <header className="mb-8 text-center">
        <h1 className="text-4xl font-extrabold tracking-tight lg:text-5xl">
          Team Skills Matcher
        </h1>
        <p className="text-lg text-muted-foreground mt-2">
          Phase {currentPhase === PHASES.PLANNING ? '1: Project Planning' : '2: Gather Team Data'}
        </p>
      </header>

      {currentPhase === PHASES.PLANNING && (
        <ProjectPlanningChat onDonePlanning={handleDonePlanning} />
      )}
      
      {currentPhase === PHASES.TEAM_INPUT && (
        <TeamInputForm /* onProcessData={...} */ />
      )}

      <footer className="mt-12 text-center text-sm text-muted-foreground">
        Powered by Gemini & Next.js
      </footer>
    </div>
  );
}