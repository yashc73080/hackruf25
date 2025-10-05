'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Card, CardHeader, CardContent, CardFooter } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Send, Loader2 } from 'lucide-react';

const PROMPT_THRESHOLD = 5; // Initial model message (1) + 2 back-and-forth exchanges (2 user, 2 model) = 5 messages total.

const initialMessages = [
  { 
    id: 1, 
    role: 'model', 
    content: "Hello! I'm your Project Planner AI. Describe your rough project idea to me, and I'll help you refine it into detailed product specifications for your team." 
  }
];

export default function ProjectPlanningChat({ onDonePlanning }) {
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Check if the user has already confirmed to move on
  const hasConfirmedDelegation = messages.some(
    (msg) => msg.role === 'user' && msg.content.toLowerCase().trim() === 'yes'
  );
  
  const sendMessage = async (e) => {
    e.preventDefault();
    // Disable sending if loading or already confirmed
    if (!input.trim() || isLoading || hasConfirmedDelegation) return;

    const userMessageContent = input.trim();
    const newMessage = { id: Date.now(), role: 'user', content: userMessageContent };
    const newMessages = [...messages, newMessage];
    
    // Check if the user is confirming the end of planning
    const isDelegatingConfirmation = userMessageContent.toLowerCase().trim() === 'yes';
    
    // Special handling for confirmation message: skip API call and transition
    if (isDelegatingConfirmation) {
        setMessages(newMessages);
        setInput('');
        
        // Extract the second-to-last message which should contain the specifications
        // This is the last model message before the temporary prompt
        const modelMessages = messages.filter(msg => msg.role === 'model');
        const specificationsMessage = modelMessages[modelMessages.length - 1]; // Last model message contains specs
        
        console.log('Extracted specifications:', specificationsMessage);
        
        // Add a final confirmation message from the bot before transitioning
        const confirmationMessage = {
            id: Date.now() + 1,
            role: 'model',
            content: 'Acknowledged. Moving to the Team Input phase now!',
        };
        
        setMessages(prev => [...prev, confirmationMessage]);

        // Pass the specifications to the parent component
        setTimeout(() => onDonePlanning(specificationsMessage), 500); 
        return;
    }
    
    // Standard conversation flow
    setInput(''); // Clear input immediately
    setMessages(newMessages);
    setIsLoading(true);

    try {
      // API call to the Next.js API Route
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: newMessages }),
      });

      if (!response.ok) {
        throw new Error('Chat API failed to respond.');
      }

      const data = await response.json();
      
      setMessages(prev => [
        ...prev, 
        { id: Date.now() + 1, role: 'model', content: data.content }
      ]);

    } catch (error) {
      console.error(error);
      setMessages(prev => [
        ...prev, 
        { id: Date.now() + 1, role: 'model', content: 'Sorry, I ran into an error. Please try again.' }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Scroll to the latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Determine if it's the exact moment to display the bot's prompt message (after the 2nd exchange)
  const showPromptMessage = messages.length === PROMPT_THRESHOLD && messages[messages.length - 1].role === 'model';
  
  // Determine if the "Yes" button should be displayed
  // It should be displayed if:
  // 1. The conversation has reached or passed the threshold (i.e., we've prompted at least once).
  // 2. The user has NOT yet sent the "Yes" confirmation message.
  const showYesButton = messages.length >= PROMPT_THRESHOLD && !hasConfirmedDelegation;

  // Conditionally create a temporary message object for display when it's time to prompt
  const displayPromptMessage = showPromptMessage ? { 
    id: 9999, 
    role: 'model', 
    content: 'Are you ready to start delegating tasks?',
    isTemporary: true
  } : null;

  return (
    <Card className="w-full max-w-4xl mx-auto shadow-xl h-[70vh] flex flex-col">
      <CardHeader className="border-b">
        <h2 className="text-xl font-bold">Project Planning Chat</h2>
      </CardHeader>

      {/* Chat Messages Area */}
      <CardContent className="flex-grow overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[70%] p-3 rounded-xl shadow-md ${
                message.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-foreground'
              }`}
            >
              <p className="whitespace-pre-wrap">{message.content}</p>
            </div>
          </div>
        ))}
        
        {/* Temporary Prompt Message, shown once at the threshold */}
        {displayPromptMessage && (
            <div
                key={displayPromptMessage.id}
                className={`flex justify-start`}
            >
                <div
                    className={`max-w-[70%] p-3 rounded-xl shadow-md bg-muted text-foreground`}
                >
                    <p className="whitespace-pre-wrap">{displayPromptMessage.content}</p>
                </div>
            </div>
        )}
        
        <div ref={messagesEndRef} />
      </CardContent>

      {/* Input and Action Buttons */}
      <CardFooter className="flex flex-col border-t p-4 space-y-3">
        {showYesButton && (
          <Button 
            type="button" // Important to prevent form submission
            className="w-full" 
            onClick={() => setInput('Yes')} // Autofill the input box with "Yes"
            disabled={isLoading}
          >
            Yes
          </Button>
        )}
        
        <form onSubmit={sendMessage} className="flex w-full space-x-2">
          <Input
            placeholder="What kind of project are you building?..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isLoading || hasConfirmedDelegation}
            className="flex-grow"
          />
          <Button type="submit" disabled={isLoading || hasConfirmedDelegation} size="icon">
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </form>
      </CardFooter>
    </Card>
  );
}