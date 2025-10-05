"use client";

import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
// Removed ArrowLeft icon to mirror Phase 2 button style (uses text arrow)

// Helper to render an array as a list
function List({ title, items }) {
  if (!items || !items.length) return null;
  return (
    <details className="border rounded-md p-3 bg-muted/30" open={false}>
      <summary className="cursor-pointer font-semibold select-none">{title}</summary>
      <ul className="list-disc pl-6 mt-2 space-y-1 text-xs">
        {items.map((it, i) => (
          <li key={i}>{it}</li>
        ))}
      </ul>
    </details>
  );
}

// Helper to render an array as comma-separated inside a dropdown (for members)
function CommaList({ title, items }) {
  if (!items || !items.length) return null;
  const text = items.map((it) => String(it)).join(', ');
  return (
    <details className="border rounded-md p-3 bg-muted/30">
      <summary className="cursor-pointer font-semibold select-none">{title}</summary>
      <p className="mt-2 text-sm">{text}</p>
    </details>
  );
}

// Roles accordion item
function RoleItem({ role, index }) {
  if (!role) return null;
  return (
    <details className="border rounded-md p-3 bg-muted/20">
      <summary className="cursor-pointer font-medium select-none">
        {index != null ? `Role ${index + 1}: ` : ''}
        <span className="text-indigo-600 dark:text-indigo-400 font-semibold">{role.title || 'Role'}</span>
      </summary>
      <div className="mt-2 space-y-3">
        {role.purpose && (
          <p className="text-sm text-foreground"><span className="font-semibold">Purpose: </span>{role.purpose}</p>
        )}
        <List title="Responsibilities" items={role.responsibilities} />
        <List title="Core Skills" items={role.core_skills} />
        <List title="Nice to Have" items={role.nice_to_have} />
        {role.collaboration_notes && (
          <details className="border rounded-md p-3 bg-muted/30">
            <summary className="cursor-pointer font-semibold select-none">Collaboration Notes</summary>
            <p className="mt-2 whitespace-pre-wrap">{role.collaboration_notes}</p>
          </details>
        )}
      </div>
    </details>
  );
}

// Member card
function toArray(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === 'string') return [value];
  if (typeof value === 'object') {
    // Flatten object values if it's a map of arrays/strings
    const vals = Object.values(value).flat();
    return vals.map((v) => (typeof v === 'string' ? v : JSON.stringify(v)));
  }
  return [];
}

function getPath(obj, path) {
  return path.split('.').reduce((acc, key) => (acc && acc[key] != null ? acc[key] : undefined), obj);
}

function firstNonEmptyArray(obj, paths) {
  for (const p of paths) {
    const val = getPath(obj, p);
    const arr = toArray(val).filter(Boolean);
    if (arr.length) return arr;
  }
  return [];
}

function uniqueStrings(arr) {
  return Array.from(new Set(arr.map((v) => String(v).trim()).filter(Boolean)));
}

// Helper: find which path produced the first non-empty array (for debugging)
// findFirstPath was used only for debug logging; removed to reduce noise

function MemberCard({ member, index }) {
  if (!member) return null;
  const name = member.name || 'Member';
  const gh = member.github_username || member.githubUsername || '';
  // Try multiple shapes/paths for each category
  const languagesPaths = [
    'languages',
    'programming_languages',
    'programmingLanguages',
    'langs',
    'extracted.languages',
    'resume.languages',
    'skills.languages',
  ];
  const languages = uniqueStrings(firstNonEmptyArray(member, languagesPaths));

  const skillsPathsList = [
    ['skills'],
    ['technical_skills'],
    ['technicalSkills'],
    ['extracted.skills.technical'],
    ['resume_skills.technical'],
    ['github_skills'],
    ['extracted.skills'],
  ];
  const skills = uniqueStrings([
    ...firstNonEmptyArray(member, skillsPathsList[0]),
    ...firstNonEmptyArray(member, skillsPathsList[1]),
    ...firstNonEmptyArray(member, skillsPathsList[2]),
    ...firstNonEmptyArray(member, skillsPathsList[3]),
    ...firstNonEmptyArray(member, skillsPathsList[4]),
    ...firstNonEmptyArray(member, skillsPathsList[5]),
    ...firstNonEmptyArray(member, skillsPathsList[6]),
  ]);

  const keywordsPathsList = [
    ['keywords'],
    ['notable_keywords'],
    ['notableKeywords'],
    ['extracted.keywords'],
    ['resume_keywords'],
  ];
  const keywords = uniqueStrings([
    ...firstNonEmptyArray(member, keywordsPathsList[0]),
    ...firstNonEmptyArray(member, keywordsPathsList[1]),
    ...firstNonEmptyArray(member, keywordsPathsList[2]),
    ...firstNonEmptyArray(member, keywordsPathsList[3]),
    ...firstNonEmptyArray(member, keywordsPathsList[4]),
  ]);
  // Debug logging removed for production cleanliness

  return (
    <Card className="shadow-md">
      <CardHeader>
        <CardTitle className="text-lg font-bold">
          <span className="text-primary">{`Member ${typeof index === 'number' ? index + 1 : ''}:`}</span>{' '}
          <span className="text-indigo-600 dark:text-indigo-400">
            {name}
            {gh ? ` (${gh})` : ''}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <CommaList title="Programming Languages" items={languages} />
        <CommaList title="Technical Skills" items={skills} />
        <CommaList title="Notable Keywords" items={keywords} />
      </CardContent>
    </Card>
  );
}

export default function ProjectOverview({ specifications, roles = [], members = [], onBackToTeam, onProceedToMatch, topK = 10, onTopKChange, canProceed = false }) {
  const ideaTitle = (specifications && (specifications.idea_title || specifications.title)) || null;
  const ideaSummary = (specifications && (specifications.idea_summary || specifications.summary)) || null;

  // We intentionally skip rendering additional spec dropdowns; focus on roles and members
  // Debug logging removed for production cleanliness

  return (
  <div className="w-full mx-auto max-w-full sm:max-w-3xl md:max-w-5xl lg:max-w-6xl xl:max-w-7xl space-y-6">
      {/* Phase 3 header actions (match Phase 2 style) */}
      <div className="w-full mx-auto max-w-full sm:max-w-3xl md:max-w-5xl lg:max-w-6xl xl:max-w-7xl mb-3 flex items-center justify-between">
        <div>
          {typeof onBackToTeam === 'function' && (
            <Button type="button" variant="outline" onClick={onBackToTeam}>
              ← Back to Team Input
            </Button>
          )}
        </div>
        <div>
          {typeof onProceedToMatch === 'function' && (
            <Button type="button" onClick={onProceedToMatch} disabled={!canProceed}>
              Proceed to Role Matching
            </Button>
          )}
        </div>
      </div>
      {/* Project Idea */}
  <Card className="shadow-xl">
        <CardHeader className="pb-1">
          <div className="flex items-center justify-between">
            <CardTitle className="text-2xl font-bold">
              Project Idea{ideaTitle ? (
                <>
                  : <span className="text-indigo-600 dark:text-indigo-400 font-semibold">{` ${ideaTitle}`}</span>
                </>
              ) : ''}
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent className="pt-0 space-y-3">
          {ideaSummary && (
            <p className="text-black font-medium whitespace-pre-wrap leading-relaxed">{ideaSummary}</p>
          )}
          {/* Roles embedded under the idea summary */}
          {roles?.length > 0 && (
            <div className="mt-2 space-y-3">
              {roles.map((r, i) => (
                <RoleItem role={r} index={i} key={i} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Removed standalone Roles card; roles now shown in the Project Idea card */}

      {/* Members */}
      {members?.length > 0 && (
        <div className="space-y-4">
          {members.map((m, idx) => (
            <MemberCard member={m} index={idx} key={m.id || idx} />
          ))}
          {/* Top-K control and proceed to role matching */}
          <div className="pt-2 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <div className="flex items-center gap-2 sm:flex-1">
              <label htmlFor="topK" className="text-sm font-medium whitespace-nowrap">Top K per category</label>
              <Input
                id="topK"
                type="number"
                min={1}
                max={100}
                step={1}
                value={topK}
                onChange={(e) => {
                  const v = parseInt(e.target.value || '10', 10);
                  if (onTopKChange) onTopKChange(Number.isFinite(v) ? Math.max(1, Math.min(100, v)) : 10);
                }}
                className="w-28"
              />
              <span className="text-xs text-muted-foreground">
                Uses strongest top-K from skills, languages, and keywords; skills and languages are weighted higher than keywords.
              </span>
            </div>
            <Button onClick={onProceedToMatch} disabled={!canProceed} className="sm:flex-none w-full sm:w-auto">
              Match roles to members
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
