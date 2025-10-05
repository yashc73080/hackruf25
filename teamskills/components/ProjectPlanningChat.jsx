'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Card, CardHeader, CardContent, CardFooter } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Send, Loader2 } from 'lucide-react';

const PROMPT_THRESHOLD = 5; // Initial model message (1) + 2 back-and-forth exchanges (2 user, 2 model) = 5 messages total.
const DELEGATION_CONFIRMATION_TEXT = 'Yes, I am ready to start delegating tasks.';

const defaultMessages = [
  { 
    id: 1, 
    role: 'model', 
    content: "Hello! I'm your Project Planner AI. Describe your rough project idea to me, and I'll help you refine it into detailed product specifications for your team." 
  }
];

export default function ProjectPlanningChat({ onUserMessage, onSpecificationsGenerated, onProceed, canProceed }) {
  const [messages, setMessages] = useState(defaultMessages);
  const nextMsgIdRef = useRef(2);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Check if the user has already confirmed to move on (with the exact confirmation phrase)
  const hasConfirmedDelegation = messages.some(
    (msg) => msg.role === 'user' && msg.content.trim().toLowerCase() === DELEGATION_CONFIRMATION_TEXT.toLowerCase()
  );

  // Keep component mounted and stateful across phases; no external restoration
  
  const sendMessage = async (e) => {
    e.preventDefault();
    // Disable sending only if loading or empty
    if (!input.trim() || isLoading) return;

    const userMessageContent = input.trim();
  const newMessage = { id: nextMsgIdRef.current++, role: 'user', content: userMessageContent };
    const newMessages = [...messages, newMessage];
  if (typeof onUserMessage === 'function') onUserMessage();
    
  // Check if the user is confirming the end of planning using the exact phrase
  const isDelegatingConfirmation = userMessageContent.trim().toLowerCase() === DELEGATION_CONFIRMATION_TEXT.toLowerCase();
    
  // Special handling for confirmation message: call backend to extract specifications and mark ready (no auto-navigation)
    if (isDelegatingConfirmation) {
        setMessages(newMessages);
        setInput('');

        // Send full chat transcript to backend for specification extraction
        try {
          const res = await fetch('/api/extract-specifications', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: newMessages }),
          });
          if (!res.ok) throw new Error('Failed to extract specifications');
          const specData = await res.json();
          const specifications = specData?.data || specData; // prefer data field

          console.log('Extracted specifications (backend):', specifications);

          // Add a final confirmation message from the bot
      const confirmationMessage = {
        id: nextMsgIdRef.current++,
              role: 'model',
              content: 'Acknowledged. Specifications generated. You can proceed when ready.',
          };
          setMessages(prev => [...prev, confirmationMessage]);
          // Notify parent that specifications are generated and ready for next phase
          if (typeof onSpecificationsGenerated === 'function') {
            onSpecificationsGenerated(specifications);
          }
          // Auto-advance to next phase
          if (typeof onProceed === 'function') {
            onProceed();
          }
          return;
        } catch (err) {
          console.error('Error extracting specifications:', err);
          setMessages(prev => [
            ...prev,
            { id: Date.now() + 1, role: 'model', content: 'Sorry, I could not extract specifications. Please try again.' }
          ]);
          return;
        }
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
        { id: nextMsgIdRef.current++, role: 'model', content: data.content }
      ]);

    } catch (error) {
      console.error(error);
      setMessages(prev => [
        ...prev, 
        { id: nextMsgIdRef.current++, role: 'model', content: 'Sorry, I ran into an error. Please try again.' }
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
  // Show the prompt once we've reached at least 4 messages and the last is from the model
  const showPromptMessage = messages.length >= 4 && messages[messages.length - 1]?.role === 'model';
  
  // Determine if the "Yes" button should be displayed
  // It should be displayed if:
  // 1. The conversation has reached or passed the threshold (i.e., we've prompted at least once).
  // 2. The user has NOT yet sent the "Yes" confirmation message.
  // Show Yes button whenever there are at least 4 messages in the chat
  const showYesButton = messages.length >= 4;

  // Conditionally create a temporary message object for display when it's time to prompt
  const displayPromptMessage = showPromptMessage ? { 
    id: 9999, 
    role: 'model', 
    content: 'Are you ready to start delegating tasks?',
    isTemporary: true
  } : null;

  return (
  <Card className="w-full mx-auto max-w-full sm:max-w-3xl md:max-w-5xl lg:max-w-6xl xl:max-w-7xl shadow-xl h-[70vh] flex flex-col">
      <CardHeader className="border-b flex flex-row items-center justify-between">
        <h2 className="text-xl font-bold">Project Planning Chat</h2>
        <Button type="button" onClick={onProceed} disabled={!canProceed}>
          Proceed to Team Input
        </Button>
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
            onClick={() => setInput(DELEGATION_CONFIRMATION_TEXT)} // Autofill the input box with the exact confirmation phrase
            disabled={isLoading}
          >
            {DELEGATION_CONFIRMATION_TEXT}
          </Button>
        )}
        
        <form onSubmit={sendMessage} className="flex w-full space-x-2">
          <Input
            placeholder="What kind of project are you building?..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isLoading}
            className="flex-grow"
          />
          <Button
            type="submit"
            disabled={isLoading}
            size="icon"
            className={`${isLoading ? 'opacity-70 cursor-not-allowed' : ''} relative`}
            aria-busy={isLoading}
          >
            {/* Keep space stable; swap icons */}
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </form>
      </CardFooter>
    </Card>
  );
}