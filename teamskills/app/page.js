"use client";

import { useState } from 'react';
import ProjectPlanningChat from '@/components/ProjectPlanningChat';
import TeamInputForm from '@/components/TeamInputForm';
import ProjectOverview from '@/components/ProjectOverview';
import RoleMatchResults from '@/components/RoleMatchResults';

const PHASES = {
  PLANNING: 'planning',
  TEAM_INPUT: 'team-input',
  OVERVIEW: 'overview',
  MATCHED: 'matched',
};

export default function Home() {
  const [currentPhase, setCurrentPhase] = useState(PHASES.PLANNING);
  // Finalized outputs
  const [finalSpecifications, setFinalSpecifications] = useState(null);
  const [finalMembers, setFinalMembers] = useState([]);
  const [finalRoles, setFinalRoles] = useState([]);
  // Dirty/ready flags per phase
  const [planningDirty, setPlanningDirty] = useState(false);
  const [specsReady, setSpecsReady] = useState(false);
  const [teamDirty, setTeamDirty] = useState(false);
  const [teamReady, setTeamReady] = useState(false);
  const [roleAssignments, setRoleAssignments] = useState({});
  const [roleReports, setRoleReports] = useState([]);
  const [matchDebug, setMatchDebug] = useState(null);
  const [topK, setTopK] = useState(10);
  // Phase navigation
  const goToPlanning = () => setCurrentPhase(PHASES.PLANNING);
  const goToTeamInput = () => setCurrentPhase(PHASES.TEAM_INPUT);
  const goToOverview = () => setCurrentPhase(PHASES.OVERVIEW);
  const goToMatched = () => setCurrentPhase(PHASES.MATCHED);
  const goBackToOverview = () => setCurrentPhase(PHASES.OVERVIEW);

  // Planning events
  const handlePlanningMessage = () => {
    // A new chat message invalidates downstream phases until regeneration
    setPlanningDirty(true);
    setSpecsReady(false);
    setFinalSpecifications(null);
    // Do NOT reset team/member state; preserve inputs across planning edits
    // We intentionally keep teamReady, finalMembers, and finalRoles intact so the user doesn't lose entries
  };

  const handleSpecificationsGenerated = (specs) => {
    setFinalSpecifications(specs);
    setSpecsReady(true);
    setPlanningDirty(false);
  };

  // Note: navigation occurs imperatively after team processing completes
  const handleProceedToMatch = async () => {
    try {
      const payload = {
        roles: finalRoles,
        members: finalMembers,
        topK,
      };
      const res = await fetch('/api/match-roles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    const data = await res.json();
      if (!res.ok || !data?.success) throw new Error(data?.error || 'Failed to match roles');
  const assignments = data.data?.assignments || {};
  const reports = data.data?.reports || [];
  const debug = data.data?.debug || {};
  // Print a single JSON object with the exact inputs used for embeddings (top-k arrays per member)
  try {
    console.log({
      event: 'role_matching_inputs',
      topK,
      debug,
    });
  } catch (_) {}
      setRoleAssignments(assignments);
  setRoleReports(reports);
    setMatchDebug(debug || null);
      // Auto-advance to matched view
      setTimeout(() => {
        goToMatched();
      }, 0);
    } catch (e) {
      alert(`Error matching roles: ${e.message}`);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 sm:p-8 md:p-12 bg-background">
      <header className="mb-8 text-center">
        <h1 className="text-4xl font-extrabold tracking-tight lg:text-5xl">
          SkillSync: AI-Powered Team Role Assignment
        </h1>
        <p className="text-lg text-muted-foreground mt-2">
          {currentPhase === PHASES.PLANNING && 'Phase 1: Project Planning'}
          {currentPhase === PHASES.TEAM_INPUT && 'Phase 2: Gather Team Data'}
          {currentPhase === PHASES.OVERVIEW && 'Phase 3: Project Overview'}
        </p>
      </header>

      {/* Keep all phases mounted; toggle visibility via CSS to preserve state */}
      <div className={currentPhase === PHASES.PLANNING ? 'w-full' : 'hidden'}>
        <ProjectPlanningChat
          onUserMessage={handlePlanningMessage}
          onSpecificationsGenerated={handleSpecificationsGenerated}
          onProceed={goToTeamInput}
          canProceed={specsReady && !planningDirty}
        />
      </div>

      <div className={currentPhase === PHASES.TEAM_INPUT ? 'w-full' : 'hidden'}>
        <TeamInputForm
          finalSpecifications={finalSpecifications}
          onBackToPlanning={goToPlanning}
          onTeamProcessed={(payload) => {
            const { members = [], roles = [], specifications = finalSpecifications, ready = false } = payload || {};
            setFinalMembers(members);
            setFinalRoles(roles);
            if (specifications) setFinalSpecifications(specifications);
            setTeamReady(!!ready);
            setTeamDirty(false);
            // Navigate to Overview only once after processing completes
            if (ready) {
              setTimeout(() => {
                goToOverview();
              }, 0);
            }
          }}
          onDirtyChange={(dirty) => setTeamDirty(!!dirty)}
          onProceed={goToOverview}
          canProceed={teamReady && !teamDirty && !planningDirty}
        />
      </div>

      <div className={currentPhase === PHASES.OVERVIEW ? 'w-full' : 'hidden'}>
        <ProjectOverview
          specifications={finalSpecifications}
          roles={finalRoles}
          members={finalMembers}
          onBackToTeam={goToTeamInput}
          onProceedToMatch={handleProceedToMatch}
          topK={topK}
          onTopKChange={setTopK}
          canProceed={teamReady && !planningDirty && !teamDirty}
        />
      </div>

      <div className={currentPhase === PHASES.MATCHED ? 'w-full' : 'hidden'}>
        <RoleMatchResults
          assignments={roleAssignments}
          roles={finalRoles}
          members={finalMembers}
          reports={roleReports}
          matchDebug={matchDebug}
          topK={topK}
          onBackToOverview={goBackToOverview}
        />
      </div>
    </div>
  );
}