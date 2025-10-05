"use client";

import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

export default function RoleMatchResults({ assignments = {}, roles = [], members = [], reports = [] }) {
  const roleTitles = Array.isArray(roles)
    ? roles.map((r, i) => r?.title || r?.name || `Role ${i + 1}`)
    : Object.keys(roles || {});

  return (
    <Card className="w-full mx-auto max-w-full sm:max-w-3xl md:max-w-5xl lg:max-w-6xl xl:max-w-7xl shadow-xl">
      <CardHeader>
        <CardTitle className="text-2xl font-bold">Final Role Assignments</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {roleTitles.length === 0 && <p className="text-muted-foreground">No roles to display.</p>}
        {roleTitles.map((title, idx) => {
          const person = assignments?.[title];
          const report = Array.isArray(reports) ? reports.find(r => r.role === title) : null;
          const candidates = report?.candidates || [];
          // Prefer softmax_percent (sharper separation); fallback to percent
          const visible = candidates
            .map(c => ({ ...c, soft: typeof c?.softmax_percent === 'number' ? c.softmax_percent : c.percent }))
            .filter(c => (c.soft ?? 0) > 0);
          const palette = [
            'bg-green-500', 'bg-green-400', 'bg-lime-400', 'bg-yellow-400',
            'bg-orange-400', 'bg-amber-500', 'bg-red-500', 'bg-rose-500'
          ];
          return (
            <div key={idx} className="border rounded-md p-3 bg-muted/20">
              <div className="font-semibold">
                <span className="text-primary">{`Role ${idx + 1}:`}</span>{' '}
                <span className="text-indigo-600 dark:text-indigo-400">{title}</span>
              </div>
              <div className="mt-1 text-sm">
                Assigned to:{' '}
                <span className="font-medium">{person || 'Unassigned'}</span>
              </div>
              {visible.length > 0 && (
                <div className="mt-3">
                  <div className="w-full h-6 rounded overflow-hidden flex border">
                    {visible.map((c, i) => (
                      <div
                        key={i}
                        className={`${palette[i % palette.length]} h-full`}
                        style={{ width: `${(c.soft * 100).toFixed(2)}%` }}
                        title={`${c.member} (${(c.soft * 100).toFixed(1)}%)`}
                      />
                    ))}
                  </div>
                  <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-1 text-xs">
                    {visible.map((c, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <span className={`inline-block w-3 h-3 rounded ${palette[i % palette.length]}`} />
                        <span className="truncate">
                          {c.member} — softmax {(c.soft * 100).toFixed(1)}% {typeof c.score === 'number' ? `(cos ${c.score.toFixed(3)})` : ''}
                        </span>
                      </div>
                    ))}
                  </div>
                  {report?.log && (
                    <p className="mt-2 text-xs text-muted-foreground">{report.log}</p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
