import { NextResponse } from 'next/server';
import { writeFile, mkdir } from 'fs/promises';
import path from 'path';

// Add this GET handler for browser testing
export async function GET() {
  return NextResponse.json({
    message: "Process Team Data API is running!",
    endpoint: "/api/process-team-data",
    methods: ["GET", "POST"],
    description: "Use POST to submit team data with resumes",
    timestamp: new Date().toISOString()
  });
}

export async function POST(req) {
  try {
    const formData = await req.formData();
    const specifications = JSON.parse(formData.get('specifications'));
    const teamMembersCount = parseInt(formData.get('teamMembersCount'));
    
    console.log('=== PROCESSING TEAM DATA ===');
    console.log('Raw specifications:', formData.get('specifications'));
    console.log('Parsed specifications:', specifications);
    console.log('Team members count:', teamMembersCount);
    
    // Create uploads directory if it doesn't exist
    const uploadsDir = path.join(process.cwd(), '.cache', 'resumes');
    await mkdir(uploadsDir, { recursive: true });
    
    const processedMembers = [];
    
    // Process each team member
    for (let i = 0; i < teamMembersCount; i++) {
      const member = {
        id: formData.get(`member_${i}_id`),
        name: formData.get(`member_${i}_name`),
        githubUsername: formData.get(`member_${i}_githubUsername`) || '',
      };
      
      console.log(`Processing member ${i}:`, member);
      
      const resumeFile = formData.get(`member_${i}_resumeFile`);
      
      if (resumeFile && resumeFile.size > 0) {
        console.log(`Resume file for ${member.name}:`, {
          name: resumeFile.name,
          size: resumeFile.size,
          type: resumeFile.type
        });
        
        // Generate a safe filename
        const timestamp = Date.now();
        const safeName = member.name.replace(/[^a-zA-Z0-9]/g, '_');
        const fileExtension = path.extname(resumeFile.name);
        const fileName = `${safeName}_${timestamp}${fileExtension}`;
        const filePath = path.join(uploadsDir, fileName);
        
        // Save the file
        const bytes = await resumeFile.arrayBuffer();
        const buffer = Buffer.from(bytes);
        await writeFile(filePath, buffer);
        
        member.resumeFilePath = filePath;
        member.resumeFileName = fileName;
        
        console.log(`✅ Saved resume: ${fileName} for ${member.name}`);
      }
      
      processedMembers.push(member);
    }
    
    console.log('✅ All team members processed:', processedMembers);
    
    // Return detailed response including all received data
    const responseData = {
      success: true, 
      message: 'Team data processed successfully',
      receivedData: {
        specifications: specifications,
        teamMembersCount: teamMembersCount,
        teamMembers: processedMembers,
        resumesLocation: uploadsDir
      },
      debug: {
        formDataKeys: Array.from(formData.keys()),
        timestamp: new Date().toISOString()
      }
    };
    
    console.log('📤 Sending response:', responseData);
    
    return NextResponse.json(responseData);
    
  } catch (error) {
    console.error('❌ Error processing team data:', error);
    return NextResponse.json(
      { success: false, error: error.message, stack: error.stack },
      { status: 500 }
    );
  }
}