import { NextResponse } from 'next/server';
import { writeFile, mkdir } from 'fs/promises';
import path from 'path';

export const runtime = 'nodejs';

export async function POST(req) {
  try {
    const form = await req.formData();
    const file = form.get('file');
    const memberId = form.get('memberId') || 'member';
    const memberName = form.get('name') || '';

    if (!(file instanceof File) || file.size === 0) {
      return NextResponse.json({ success: false, error: 'No file provided' }, { status: 400 });
    }

    // Ensure .cache/resumes exists under the Next.js app working directory
    const cacheDir = path.join(process.cwd(), '.cache', 'resumes');
    await mkdir(cacheDir, { recursive: true });

    // Build a safe filename
    const safeName = String(memberName || memberId).replace(/[^a-zA-Z0-9_-]/g, '_');
    const ext = path.extname(file.name) || '.pdf';
    const filename = `${safeName}_${Date.now()}${ext}`;
    const dest = path.join(cacheDir, filename);

    const bytes = new Uint8Array(await file.arrayBuffer());
    await writeFile(dest, bytes);

    // Return both absolute and relative paths; backend can use absPath
    return NextResponse.json({
      success: true,
      filename,
      relPath: path.join('.cache', 'resumes', filename),
      absPath: dest,
    });
  } catch (error) {
    console.error('❌ Upload failed:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
