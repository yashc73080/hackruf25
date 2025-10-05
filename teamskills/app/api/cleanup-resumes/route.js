export async function POST() {
  try {
    const fs = (await import('fs/promises')).default;
    const path = (await import('path')).default;

    // Resolve the resumes cache folder relative to the project root
    const baseDir = process.cwd();
    const resumesDir = path.join(baseDir, 'teamskills', '.cache', 'resumes');

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
    await Promise.all(
      entries.map(async (name) => {
        const p = path.join(resumesDir, name);
        try {
          const stat = await fs.stat(p);
          if (stat.isFile()) {
            await fs.unlink(p);
            deleted += 1;
          } else if (stat.isDirectory()) {
            // Recursively remove subfolders if any
            await fs.rm(p, { recursive: true, force: true });
            deleted += 1;
          }
        } catch (_) {
          // Ignore failures for individual entries
        }
      })
    );

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
