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

    const newMessage = { id: Date.now(), role: 'user', content: input.trim() };
    const newMessages = [...messages, newMessage];
    
    setMessages(newMessages);
    setInput('');
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

  // Check if the plan is ready (example condition: bot confirms readiness)
  const isPlanReady = messages.some(
    (msg) => msg.role === 'model' && msg.content.toLowerCase().includes('plan is finalized')
  );

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
        <div ref={messagesEndRef} />
      </CardContent>

      {/* Input and Action Buttons */}
      <CardFooter className="flex flex-col border-t p-4 space-y-3">
        {isPlanReady ? (
          <Button 
            className="w-full" 
            onClick={onDonePlanning} // Function passed from parent to advance phase
            disabled={isLoading}
          >
            <Check className="mr-2 h-4 w-4" /> Done Planning! Go to Team Input
          </Button>
        ) : (
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
        )}
      </CardFooter>
    </Card>
  );
}