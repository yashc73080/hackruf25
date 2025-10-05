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
  name: '',
  githubUsername: '',
  resumeFile: null,
};

export default function TeamInputForm({ finalSpecifications }) {
  const [teamMembers, setTeamMembers] = useState([initialMember]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const addMember = () => {
    const newMember = { ...initialMember, id: Date.now() };
    setTeamMembers(prev => [...prev, newMember]);
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
    
    // Updated validation: at least one member, all must have a name and resume file
    const isValid = teamMembers.length > 0 && teamMembers.every(m => m.name.trim() && m.resumeFile);
    if (!isValid) {
        alert('Please ensure all team members have a name and uploaded resume.');
        return;
    }

    setIsSubmitting(true);

    try {
      // Create FormData to handle file uploads
      const formData = new FormData();
      
      // Add specifications
      formData.append('specifications', JSON.stringify(finalSpecifications));
      formData.append('teamMembersCount', teamMembers.length.toString());
      
      // Add each team member's data
      teamMembers.forEach((member, index) => {
        formData.append(`member_${index}_id`, member.id.toString());
        formData.append(`member_${index}_name`, member.name);
        formData.append(`member_${index}_githubUsername`, member.githubUsername || '');
        
        if (member.resumeFile) {
          formData.append(`member_${index}_resumeFile`, member.resumeFile);
        }
      });

      console.log('=== SENDING TEAM DATA TO API ===');
      console.log('Number of team members:', teamMembers.length);
      
      // Send to API route
      const response = await fetch('/api/process-team-data', {
        method: 'POST',
        body: formData, // Don't set Content-Type header - let browser set it for FormData
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const result = await response.json();
      
      if (result.success) {
        console.log('✅ Team data processed successfully:', result.data);
        // TODO: Move to next phase or show success message
        alert('Team data processed successfully! Check backend for role assignments.');
      } else {
        throw new Error(result.error || 'Unknown error occurred');
      }
      
    } catch (error) {
      console.error('❌ Error submitting team data:', error);
      alert(`Error processing team data: ${error.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card className="w-full max-w-4xl mx-auto shadow-xl">
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