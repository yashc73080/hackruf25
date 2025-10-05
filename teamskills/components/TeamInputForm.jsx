'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Trash2, UserPlus, Upload, Loader2, Check } from 'lucide-react';

// Initial structure for a team member (stable id to avoid SSR hydration mismatch)
const initialMember = {
  id: 'm-1',
  name: '',
  githubUsername: '',
  resumeFile: null,
  resumePath: '', // absolute path returned by upload API
};

export default function TeamInputForm({ finalSpecifications, onBackToPlanning, onTeamProcessed, onDirtyChange, onProceed, canProceed }) {
  const [teamMembers, setTeamMembers] = useState([initialMember]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const inFlightRef = useRef(false);
  const [derivedRoles, setDerivedRoles] = useState([]);
  const [isDirty, setIsDirty] = useState(false);
  const nextIdRef = useRef(2);
  
  const ideaTitle = (finalSpecifications && (finalSpecifications.idea_title || finalSpecifications.title)) || null;
  const ideaSummary = (finalSpecifications && (finalSpecifications.idea_summary || finalSpecifications.summary)) || null;
  const specObj = finalSpecifications || {};

  const addMember = () => {
    const newId = `m-${nextIdRef.current++}`;
    const newMember = { ...initialMember, id: newId };
    setTeamMembers(prev => [...prev, newMember]);
    setIsDirty(true);
  };

  const removeMember = (id) => {
    setTeamMembers(prev => prev.filter(member => member.id !== id));
    setIsDirty(true);
  };

  const updateMember = (id, field, value) => {
    setTeamMembers(prev =>
      prev.map(member =>
        member.id === id ? { ...member, [field]: value } : member
      )
    );
    setIsDirty(true);
  };

  const handleResumeChange = (member, file) => {
    // Only store the file now; upload will occur on submit
    updateMember(member.id, 'resumeFile', file);
    // Clear any previous path if a new file is selected
    updateMember(member.id, 'resumePath', '');
  };

  useEffect(() => {
    if (typeof onDirtyChange === 'function') onDirtyChange(isDirty);
  }, [isDirty, onDirtyChange]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (inFlightRef.current) return; // guard against duplicate submissions
    
  // Validate: at least one member, each has a name and selected resume file
  const isValid = teamMembers.length > 0 && teamMembers.every(m => m.name.trim() && m.resumeFile);
    if (!isValid) {
        alert('Please ensure all team members have a name and uploaded resume.');
        return;
    }

    setIsSubmitting(true);
    inFlightRef.current = true;

    try {
      // 1) Upload resumes now (if not already uploaded) to get absPath
      const uploadedMembers = [];
      for (const member of teamMembers) {
        let resumePath = member.resumePath;
        if (!resumePath) {
          const file = member.resumeFile;
          if (!file) throw new Error(`No resume file for ${member.name}`);
          const fd = new FormData();
          fd.append('file', file);
          fd.append('memberId', String(member.id));
          fd.append('name', member.name || 'member');
          const res = await fetch('/api/upload-resume', { method: 'POST', body: fd });
          const data = await res.json();
          if (!res.ok || !data?.success || !data?.absPath) {
            throw new Error(data?.error || `Upload failed for ${member.name}`);
          }
          resumePath = data.absPath;
        }
        uploadedMembers.push({ ...member, resumePath });
      }

      // Optionally reflect updated paths in state (non-blocking for payload)
      setTeamMembers(uploadedMembers);

      // 2) Derive roles for the team size from specifications before skills extraction
      let rolesLocal = [];
      try {
        const rolesRes = await fetch('/api/extract-roles', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ specifications: finalSpecifications || {}, memberCount: uploadedMembers.length }),
        });
        const rolesJson = await rolesRes.json();
        if (rolesRes.ok && rolesJson?.success) {
          const roles = rolesJson.data?.roles || [];
          rolesLocal = roles;
          setDerivedRoles(roles);
          console.log('🧩 Derived roles for team:', roles);
        } else {
          console.warn('Could not derive roles:', rolesJson?.error || rolesRes.statusText);
        }
      } catch (e) {
        console.warn('Error deriving roles:', e);
      }

      // 3) Build minimal JSON payload: name, githubUsername, resumePath
      const payload = {
        specifications: finalSpecifications || [],
        teamMembersCount: uploadedMembers.length,
        members: uploadedMembers.map(m => ({
          id: m.id,
          name: m.name,
          githubUsername: m.githubUsername || '',
          resumePath: m.resumePath,
        })),
      };

      console.log('=== SENDING TEAM DATA TO API ===');
      console.log('Number of team members:', teamMembers.length);
      
      // Send to API route
      const response = await fetch('/api/process-team-data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

  const result = await response.json();

      if (result.success) {
        console.log('✅ Team data processed successfully:', result.data);
        const apiMembersRaw = result?.data?.members || result?.data?.processed_members || [];
        console.log('ℹ️ API members array name:', result?.data?.members ? 'members' : (result?.data?.processed_members ? 'processed_members' : 'none'));
        console.log('ℹ️ API members count:', Array.isArray(apiMembersRaw) ? apiMembersRaw.length : 'not-array');
        // Prepare overview payload
        const normalizeMember = (m) => {
          const languages = m.languages || m.programming_languages || m.programmingLanguages || m.langs || (m.extracted?.languages) || [];
          const skills = m.skills || m.technical_skills || m.technicalSkills || (m.extracted?.skills?.technical) || [];
          const keywords = m.keywords || m.notable_keywords || m.notableKeywords || (m.extracted?.keywords) || [];
          const githubUsername = m.githubUsername || m.github_username || m.github || '';
          return {
            ...m,
            // Normalize common fields shape
            githubUsername,
            resumePath: m.resumePath || m.resume_path || m.resume_public_path || m.resume_url || '',
            languages,
            skills,
            keywords,
          };
        };
        const membersOut = Array.isArray(apiMembersRaw)
          ? apiMembersRaw.map(normalizeMember)
          : uploadedMembers.map(m => normalizeMember({
              id: m.id,
              name: m.name,
              githubUsername: m.githubUsername || '',
              resumePath: m.resumePath,
            }));
        const rolesOut = Array.isArray(rolesLocal) && rolesLocal.length ? rolesLocal : (Array.isArray(derivedRoles) ? derivedRoles : []);
        setIsDirty(false);
        // Determine readiness for overview: require roles present and members match count
        const hasMemberDetails = membersOut.length === uploadedMembers.length;
        const hasRoles = rolesOut.length > 0;
        const ready = !!(hasMemberDetails && hasRoles);
        // Cleanup resumes cache after successful processing
        try {
          await fetch('/api/cleanup-resumes', { method: 'POST' });
        } catch (_) {
          // non-fatal
        }
        // Clear stored resumePath to force re-upload if user changes resumes later
        setTeamMembers(prev => prev.map(m => ({ ...m, resumePath: '' })));
        if (typeof onTeamProcessed === 'function') {
          onTeamProcessed({ members: membersOut, roles: rolesOut, specifications: finalSpecifications, ready });
          // Navigation is now declarative in parent; keep manual Proceed button behavior only
        } else {
          alert('Processed successfully. No overview handler found.');
        }
      } else {
        throw new Error(result.error || 'Unknown error occurred');
      }
      
    } catch (error) {
      console.error('❌ Error submitting team data:', error);
      alert(`Error processing team data: ${error.message}`);
    } finally {
      setIsSubmitting(false);
      inFlightRef.current = false;
    }
  };

  return (
    <>
      <div className="w-full mx-auto max-w-full sm:max-w-3xl md:max-w-5xl lg:max-w-6xl xl:max-w-7xl mb-3 flex items-center justify-between">
        <div>
          {typeof onBackToPlanning === 'function' && (
            <Button type="button" variant="outline" onClick={onBackToPlanning}>
              ← Back to Planning
            </Button>
          )}
        </div>
        <div>
          {typeof onProceed === 'function' && (
            <Button type="button" onClick={onProceed} disabled={!canProceed}>
              Proceed to Overview
            </Button>
          )}
        </div>
      </div>
      {/* Project Idea section */}
      {finalSpecifications && (
        <>
          <Card className="w-full mx-auto max-w-full sm:max-w-3xl md:max-w-5xl lg:max-w-6xl xl:max-w-7xl shadow-xl mb-2">
            <CardHeader className="pb-1">
              <CardTitle className="text-2xl font-bold">
                Project Idea{ideaTitle ? (
                  <>
                    : <span className="text-indigo-600 dark:text-indigo-400 font-semibold">{` ${ideaTitle}`}</span>
                  </>
                ) : ''}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              {ideaSummary && (
                <p className="text-black font-medium whitespace-pre-wrap leading-relaxed">
                  {ideaSummary}
                </p>
              )}
              {/* Interactive specifications */}
              <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                {Array.isArray(specObj.objectives) && specObj.objectives.length > 0 && (
                  <details className="border rounded-md p-3 bg-muted/30">
                    <summary className="cursor-pointer font-semibold select-none">Objectives</summary>
                    <ul className="list-disc pl-6 mt-2 space-y-1 text-xs">
                      {specObj.objectives.map((it, i) => <li key={i}>{it}</li>)}
                    </ul>
                  </details>
                )}
                {Array.isArray(specObj.core_features) && specObj.core_features.length > 0 && (
                  <details className="border rounded-md p-3 bg-muted/30">
                    <summary className="cursor-pointer font-semibold select-none">Core Features</summary>
                    <ul className="list-disc pl-6 mt-2 space-y-1 text-xs">
                      {specObj.core_features.map((it, i) => <li key={i}>{it}</li>)}
                    </ul>
                  </details>
                )}
                {Array.isArray(specObj.stretch_goals) && specObj.stretch_goals.length > 0 && (
                  <details className="border rounded-md p-3 bg-muted/30">
                    <summary className="cursor-pointer font-semibold select-none">Stretch Goals</summary>
                    <ul className="list-disc pl-6 mt-2 space-y-1 text-xs">
                      {specObj.stretch_goals.map((it, i) => <li key={i}>{it}</li>)}
                    </ul>
                  </details>
                )}
                {Array.isArray(specObj.constraints) && specObj.constraints.length > 0 && (
                  <details className="border rounded-md p-3 bg-muted/30">
                    <summary className="cursor-pointer font-semibold select-none">Constraints</summary>
                    <ul className="list-disc pl-6 mt-2 space-y-1 text-xs">
                      {specObj.constraints.map((it, i) => <li key={i}>{it}</li>)}
                    </ul>
                  </details>
                )}
                {Array.isArray(specObj.deliverables) && specObj.deliverables.length > 0 && (
                  <details className="border rounded-md p-3 bg-muted/30">
                    <summary className="cursor-pointer font-semibold select-none">Deliverables</summary>
                    <ul className="list-disc pl-6 mt-2 space-y-1 text-xs">
                      {specObj.deliverables.map((it, i) => <li key={i}>{it}</li>)}
                    </ul>
                  </details>
                )}
                {Array.isArray(specObj.timeline_phases) && specObj.timeline_phases.length > 0 && (
                  <details className="border rounded-md p-3 bg-muted/30">
                    <summary className="cursor-pointer font-semibold select-none">Timeline Phases</summary>
                    <ul className="list-disc pl-6 mt-2 space-y-1 text-xs">
                      {specObj.timeline_phases.map((it, i) => <li key={i}>{it}</li>)}
                    </ul>
                  </details>
                )}
                {Array.isArray(specObj.risks) && specObj.risks.length > 0 && (
                  <details className="border rounded-md p-3 bg-muted/30">
                    <summary className="cursor-pointer font-semibold select-none">Risks</summary>
                    <ul className="list-disc pl-6 mt-2 space-y-1 text-xs">
                      {specObj.risks.map((it, i) => <li key={i}>{it}</li>)}
                    </ul>
                  </details>
                )}
                {Array.isArray(specObj.success_metrics) && specObj.success_metrics.length > 0 && (
                  <details className="border rounded-md p-3 bg-muted/30">
                    <summary className="cursor-pointer font-semibold select-none">Success Metrics</summary>
                    <ul className="list-disc pl-6 mt-2 space-y-1 text-xs">
                      {specObj.success_metrics.map((it, i) => <li key={i}>{it}</li>)}
                    </ul>
                  </details>
                )}
              </div>
            </CardContent>
          </Card>
          <p className="w-full mx-auto max-w-full sm:max-w-3xl md:max-w-5xl lg:max-w-6xl xl:max-w-7xl mt-2 mb-6 text-sm text-muted-foreground pl-2 md:pl-4">
            Roles will be derived to match your team size. Add teammates below and we’ll generate exactly one complementary role per person for this project.
          </p>
        </>
      )}

  <Card className="w-full mx-auto max-w-full sm:max-w-3xl md:max-w-5xl lg:max-w-6xl xl:max-w-7xl shadow-xl">
      <CardHeader>
        <CardTitle className="text-2xl font-bold text-center sm:text-left">
          Team Input: Skills & Experience
        </CardTitle>
        <CardDescription>
          Enter your teammates' information and upload their resumes to build their skill vectors.
        </CardDescription>
      </CardHeader>
      
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          {teamMembers.map((member, index) => (
            <div key={member.id} className="border p-4 rounded-lg space-y-4 bg-muted/20">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold">Team Member {index + 1}</h3>
                {teamMembers.length > 1 && (
                  <Button variant="ghost" size="sm" onClick={() => removeMember(member.id)} className="text-red-500 hover:text-red-600">
                    <Trash2 className="h-4 w-4 mr-2" /> Remove
                  </Button>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Name Input */}
                <div className="space-y-2">
                  <Label htmlFor={`name-${member.id}`}>Full Name <span className="text-red-500">*</span></Label>
                  <Input
                    id={`name-${member.id}`}
                    type="text"
                    placeholder="e.g., John Doe"
                    value={member.name}
                    onChange={(e) => updateMember(member.id, 'name', e.target.value)}
                    required
                  />
                </div>

                {/* GitHub Username Input */}
                <div className="space-y-2">
                  <Label htmlFor={`github-${member.id}`}>GitHub Username (Optional)</Label>
                  <Input
                    id={`github-${member.id}`}
                    type="text"
                    placeholder="e.g., octocat"
                    value={member.githubUsername}
                    onChange={(e) => updateMember(member.id, 'githubUsername', e.target.value)}
                  />
                </div>

                {/* Resume Upload Input - now mandatory */}
                <div className="space-y-2">
                  <Label htmlFor={`resume-${member.id}`}>Resume/CV <span className="text-red-500">*</span></Label>
                  <div className="space-y-1">
                    <Input
                      id={`resume-${member.id}`}
                      type="file"
                      accept=".pdf,image/*"
                      onChange={(e) => handleResumeChange(member, e.target.files[0])}
                      className="w-full file:text-sm file:font-medium file:mr-4 file:py-1 file:px-2 file:rounded-full file:border-0 file:bg-primary file:text-primary-foreground hover:file:bg-primary/90"
                      required
                    />
                    {member.resumeFile && (
                      <div className="text-sm text-green-600 flex items-center">
                        <Check className="h-4 w-4 mr-2" />
                        <span className="truncate">{member.resumeFile.name}</span>
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    PDF or image (PNG, JPG/JPEG, TIFF, WEBP). Used for OCR extraction of detailed skills.
                  </p>
                </div>
              </div>
            </div>
          ))}

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row justify-between pt-4 gap-4">
            <Button 
              type="button" 
              onClick={addMember} 
              variant="outline" 
              className="flex items-center w-full sm:w-auto"
            >
              <UserPlus className="h-4 w-4 mr-2" /> Add Teammate
            </Button>
            
            <Button 
              type="submit" 
              className="flex items-center w-full sm:w-auto"
              disabled={isSubmitting || teamMembers.length === 0}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Processing Data...
                </>
              ) : (
                <>
                  <Upload className="mr-2 h-4 w-4" /> Done Inputting & Process
                </>
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
    </>
  );
}