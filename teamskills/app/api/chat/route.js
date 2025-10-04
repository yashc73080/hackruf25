// This is a conceptual implementation. 
// You'll need to install the Google Gen AI SDK (`npm install @google/genai`).

import { GoogleGenAI } from '@google/genai';
import { NextResponse } from 'next/server';

// Initialize the GoogleGenAI client
// The NEXT_PUBLIC_GEMINI_API_KEY environment variable is automatically used
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

export async function POST(req) {
  try {
    const { messages } = await req.json();

    // 1. Construct the prompt with the user's conversation history
    const history = messages.map(msg => ({
      role: msg.role === 'user' ? 'user' : 'model',
      parts: [{ text: msg.content }],
    }));

    // 2. Add system instruction for idea refinement (crucial for Step 1)
    const systemInstruction = 
      "You are a Project Planner AI. Your goal is to help the user refine their rough project idea into detailed, actionable product specifications (key features, components, system requirements). Keep responses concise and focused on gathering details. When the plan is ready, signal by asking for confirmation.";
    
    // 3. Call the Gemini API
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash-lite',
      contents: history,
      config: {
        systemInstruction: systemInstruction,
      },
    });

    const botResponse = response.text.trim();

    return NextResponse.json({ 
      content: botResponse 
    });

  } catch (error) {
    console.error('Gemini API Error:', error);
    return NextResponse.json(
      { error: 'Failed to communicate with the AI model.' },
      { status: 500 }
    );
  }
}