"use client";

import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowLeft } from 'lucide-react';

export default function RoleMatchResults({ assignments = {}, roles = [], members = [], reports = [], matchDebug = null, topK, onBackToOverview }) {
  const roleTitles = Array.isArray(roles)
    ? roles.map((r, i) => r?.title || r?.name || `Role ${i + 1}`)
    : Object.keys(roles || {});

  // Helper to retrieve a member's top-k arrays from backend debug
  const memberDebugByName = React.useMemo(() => {
    const map = new Map();
    const arr = matchDebug?.members || [];
    for (const m of arr) {
      if (m?.name) map.set(m.name, m);
    }
    return map;
  }, [matchDebug]);

  // Helper to retrieve role debug (core_skills text) by role title
  const roleDebugByTitle = React.useMemo(() => {
    const map = new Map();
    const arr = matchDebug?.roles || [];
    for (const r of arr) {
      if (r?.role) map.set(r.role, r);
    }
    return map;
  }, [matchDebug]);

  return (
    <Card className="w-full mx-auto max-w-full sm:max-w-3xl md:max-w-5xl lg:max-w-6xl xl:max-w-7xl shadow-xl">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-2xl font-bold">Final Role Assignments</CardTitle>
          <Button variant="outline" onClick={onBackToOverview} disabled={!onBackToOverview} className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            Back to Overview
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {roleTitles.length === 0 && <p className="text-muted-foreground">No roles to display.</p>}
        {roleTitles.map((title, idx) => {
          const person = assignments?.[title];
          const report = Array.isArray(reports) ? reports.find(r => r.role === title) : null;
          const candidates = report?.candidates || [];
          // Use softmax-enhanced score if provided, else compute fallback softmax on client.
          const rawScores = candidates.map(c => (typeof c.score === 'number' ? c.score : 0));
          const temperature = (matchDebug?.softmax_temperature) ?? 0.6;
          const softmax = (arr, t = 1.0) => {
            if (!arr.length) return [];
            const scaled = arr.map(x => x / (t || 1));
            const m = Math.max(...scaled);
            const exps = scaled.map(x => Math.exp(x - m));
            const sum = exps.reduce((a, b) => a + b, 0) || 1;
            return exps.map(e => e / sum);
          };
          const soft = candidates.map((c, i) => (typeof c.soft_score === 'number' ? c.soft_score : softmax(rawScores, temperature)[i] || 0));
          // Prepare rows from highest soft_score (leftmost previously) to lowest (rightmost previously)
          const rows = candidates
            .map((c, i) => ({ ...c, _soft: soft[i] }))
            .sort((a, b) => b._soft - a._soft);
          // Helper: clamp to [0,1] for width and color mapping (using soft score)
          const to01 = (v) => {
            if (typeof v !== 'number' || Number.isNaN(v)) return 0;
            return Math.max(0, Math.min(1, v));
          };
          const colorFor = (p01) => {
            // Map 0 -> red (0deg), 1 -> green (120deg)
            const hue = Math.round(120 * p01);
            return `hsl(${hue} 80% 45%)`;
          };
          return (
            <div key={idx} className="border rounded-md p-3 bg-muted/20">
              <div className="font-semibold">
                <span className="text-primary">{`Role ${idx + 1}:`}</span>{' '}
                <span className="text-indigo-600 dark:text-indigo-400">{title}</span>
              </div>
              {/* Role core_skills text under the title */}
              {(() => {
                const rd = roleDebugByTitle.get(title);
                const text = rd?.text;
                if (!text) return null;
                const prefix = 'Core skills:';
                if (text.startsWith(prefix)) {
                  const rest = text.slice(prefix.length).trim();
                  return (
                    <div className="mt-1 text-xs text-muted-foreground">
                      <span className="font-semibold">{prefix}</span> {rest}
                    </div>
                  );
                }
                return <div className="mt-1 text-xs text-muted-foreground">{text}</div>;
              })()}
              {/* Assigned-to line below the role debug text */}
              <div className="mt-2 text-sm">
                Assigned to: <span className="font-medium text-indigo-600 dark:text-indigo-400">{person || 'Unassigned'}</span>
              </div>
              {rows.length > 0 && (
                <div className="mt-3 space-y-2">
                  {rows.map((c, i) => {
                    const p01 = to01(c._soft);
                    const widthPct = Math.round(p01 * 100);
                    const barColor = colorFor(p01);
                    return (
                      <div key={i} className="flex items-center gap-3">
                        <div className="flex-1">
                          <div className="relative h-5 bg-muted rounded overflow-hidden border">
                            <div
                              className="absolute left-0 top-0 h-full"
                              style={{ width: `${widthPct}%`, backgroundColor: barColor }}
                              title={`${c.member} (cos* ${typeof c._soft === 'number' ? c._soft.toFixed(3) : '0.000'})`}
                            />
                          </div>
                        </div>
                        <div className="w-56 text-xs whitespace-nowrap overflow-hidden text-ellipsis text-right">
                          <span className="font-medium">{c.member}</span>
                          <span className="text-muted-foreground">{`  (${typeof c._soft === 'number' ? c._soft.toFixed(3) : '0.000'})`}</span>
                        </div>
                      </div>
                    );
                  })}
                  {report?.log && (
                    <p className="text-xs text-muted-foreground">{report.log}</p>
                  )}
                </div>
              )}
              {/* Winner detail: print the top-k contributing arrays under the role */}
              {report?.winner && (() => {
                const md = memberDebugByName.get(report.winner);
                if (!md) return null;
                const hasAny = (md.skills && md.skills.length) || (md.languages && md.languages.length) || (md.keywords && md.keywords.length);
                if (!hasAny) return null;
                return (
                  <div className="mt-3 text-xs text-muted-foreground">
                    <div className="font-medium text-foreground">Top-K inputs for {report.winner}{typeof topK === 'number' ? ` (k=${topK})` : ''}:</div>
                    {Array.isArray(md.skills) && md.skills.length > 0 && (
                      <div className="mt-1"><span className="font-medium text-foreground">Skills:</span> {md.skills.join(', ')}</div>
                    )}
                    {Array.isArray(md.languages) && md.languages.length > 0 && (
                      <div className="mt-1"><span className="font-medium text-foreground">Languages:</span> {md.languages.join(', ')}</div>
                    )}
                    {Array.isArray(md.keywords) && md.keywords.length > 0 && (
                      <div className="mt-1"><span className="font-medium text-foreground">Keywords:</span> {md.keywords.join(', ')}</div>
                    )}
                  </div>
                );
              })()}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
