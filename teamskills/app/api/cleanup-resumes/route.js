export async function POST() {
  try {
    const fs = (await import('fs/promises')).default;
    const path = (await import('path')).default;

  // Resolve the resumes cache folder relative to the Next.js app working directory
  // Upload route stores files at `${process.cwd()}/.cache/resumes`
  const baseDir = process.cwd();
  const resumesDir = path.join(baseDir, '.cache', 'resumes');

    // Attempt to read directory; if missing, treat as success
    let entries = [];
    try {
      entries = await fs.readdir(resumesDir);
    } catch (e) {
      // Directory might not exist yet
      return new Response(JSON.stringify({ success: true, deleted: 0, note: 'No cache dir' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    let deleted = 0;
    // Remove the whole resumes directory for a clean slate
    await fs.rm(resumesDir, { recursive: true, force: true });
    deleted = entries.length;
    // Recreate the directory to keep subsequent uploads working
    await fs.mkdir(resumesDir, { recursive: true });

    return new Response(JSON.stringify({ success: true, deleted }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    return new Response(JSON.stringify({ success: false, error: String(error) }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
