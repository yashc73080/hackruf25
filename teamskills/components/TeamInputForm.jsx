'use client';

import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Trash2, UserPlus, Upload, Loader2, Check } from 'lucide-react';

// Initial structure for a team member
const initialMember = {
  id: Date.now(),
  githubUsername: '',
  resumeFile: null,
};

export default function TeamInputForm({ finalSpecifications }) {
  const [teamMembers, setTeamMembers] = useState([initialMember]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const addMember = () => {
    setTeamMembers(prev => [
      ...prev,
      { ...initialMember, id: Date.now() },
    ]);
  };

  const removeMember = (id) => {
    setTeamMembers(prev => prev.filter(member => member.id !== id));
  };

  const updateMember = (id, field, value) => {
    setTeamMembers(prev =>
      prev.map(member =>
        member.id === id ? { ...member, [field]: value } : member
      )
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Updated validation: at least one member, all must have a resume file
    const isValid = teamMembers.length > 0 && teamMembers.every(m => m.resumeFile);
    if (!isValid) {
        alert('Please ensure all team members have uploaded a resume.');
        return;
    }

    setIsSubmitting(true);

    // Prepare data for backend processing
    const dataToSend = {
      specifications: finalSpecifications, // The extracted specifications from chat
      teamMembers: teamMembers
    };

    console.log('Data ready for backend processing:', dataToSend);

    // TODO: Send dataToSend to backend API route
    // 1. Send all team member data (usernames, and resume files) 
    //    along with the project specifications
    //    to a Next.js API route (e.g., /api/process-team-data).
    // 2. The API route handles the heavy lifting (GitHub API calls, OCR, vectorization).
    // 3. Handle the response (success/failure) and move to the next UI state.

    // Simulate API call delay
    await new Promise(resolve => setTimeout(resolve, 3000)); 
    
    setIsSubmitting(false);
  };

  return (
    <Card className="w-full max-w-4xl mx-auto shadow-xl">
      <CardHeader>
        <CardTitle className="text-2xl font-bold text-center sm:text-left">
          Team Input: Skills & Experience
        </CardTitle>
        <CardDescription>
          Enter your teammates' GitHub profiles and upload their resumes to build their skill vectors.
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

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                  <div className="flex items-center space-x-2">
                    <Input
                      id={`resume-${member.id}`}
                      type="file"
                      accept=".pdf"
                      onChange={(e) => updateMember(member.id, 'resumeFile', e.target.files[0])}
                      className="flex-grow file:text-sm file:font-medium file:mr-4 file:py-1 file:px-2 file:rounded-full file:border-0 file:bg-primary file:text-primary-foreground hover:file:bg-primary/90"
                      required
                    />
                    {member.resumeFile && (
                        <div className="text-sm text-green-600 flex items-center">
                            <Check className="h-4 w-4 mr-1"/>
                            <span className="truncate max-w-[100px]">{member.resumeFile.name}</span>
                        </div>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Used for OCR extraction of detailed skills.
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
  );
}