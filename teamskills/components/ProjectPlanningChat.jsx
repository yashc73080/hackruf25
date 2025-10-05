'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Card, CardHeader, CardContent, CardFooter } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Send, Loader2 } from 'lucide-react';

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

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessageContent = input.trim();
    const newMessage = { id: Date.now(), role: 'user', content: userMessageContent };
    const newMessages = [...messages, newMessage];
    
    // Check if the user is confirming the end of planning
    const isDelegatingConfirmation = userMessageContent.toLowerCase().trim() === 'yes';
    
    // Special handling for confirmation message: skip API call and transition
    if (isDelegatingConfirmation) {
        setMessages(newMessages);
        setInput('');
        
        // Add a final confirmation message from the bot before transitioning
        const confirmationMessage = {
            id: Date.now() + 1,
            role: 'model',
            content: 'Acknowledged. Moving to the Team Input phase now!',
        };
        
        setMessages(prev => [...prev, confirmationMessage]);

        // Delay the transition slightly to allow UI to update
        setTimeout(onDonePlanning, 500); 
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

  // The chat should prompt after 2 messages of back and forth (1 initial model + 1 user + 1 model = 3 messages total).
  const isPromptTime = messages.length === 3 && messages[messages.length - 1].role === 'model';
  
  // Check if the user has already confirmed, to prevent the button from reappearing
  const isDelegating = messages.some(
    (msg) => msg.role === 'user' && msg.content.toLowerCase().trim() === 'yes'
  );

  const showPromptButton = isPromptTime && !isDelegating;
  
  // Conditionally create a temporary message object for display when it's time to prompt
  const displayPromptMessage = showPromptButton ? { 
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
        
        {/* Temporary Prompt Message */}
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
        {showPromptButton && (
          <Button 
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
            disabled={isLoading}
            className="flex-grow"
          />
          <Button type="submit" disabled={isLoading} size="icon">
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </form>
      </CardFooter>
    </Card>
  );
}