import os
import uuid
import shutil
import subprocess
import zipfile
import tempfile
from pathlib import Path
from flask import Flask, request, jsonify, send_file, Response, render_template_string

app = Flask(__name__)

ALLOWED_MODELS = {"htdemucs_6s", "htdemucs", "hdemucs_mmi"}
ALLOWED_FORMATS = {"mp3", "flac"}

UPLOAD_DIR = Path(tempfile.gettempdir()) / "stem-extractor"
UPLOAD_DIR.mkdir(exist_ok=True)

# Store job info: job_id -> {input_path, output_dir, model, format, status}
jobs = {}

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stem Extractor</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0f0f0f; color: #e0e0e0; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
  .container { width: 100%; max-width: 540px; padding: 2rem; }
  h1 { font-size: 1.5rem; margin-bottom: 1.5rem; text-align: center; }
  .drop-zone { border: 2px dashed #444; border-radius: 12px; padding: 3rem 1.5rem; text-align: center; cursor: pointer; transition: border-color 0.2s, background 0.2s; margin-bottom: 1.5rem; }
  .drop-zone.dragover { border-color: #7c6df0; background: rgba(124,109,240,0.08); }
  .drop-zone.has-file { border-color: #555; border-style: solid; }
  .drop-zone input { display: none; }
  .file-name { color: #7c6df0; font-weight: 600; margin-top: 0.5rem; word-break: break-all; }
  .settings { display: flex; gap: 1rem; margin-bottom: 1.5rem; }
  .settings label { flex: 1; }
  .settings select { width: 100%; padding: 0.5rem; border-radius: 8px; border: 1px solid #333; background: #1a1a1a; color: #e0e0e0; font-size: 0.9rem; }
  .settings span { display: block; font-size: 0.8rem; color: #888; margin-bottom: 0.3rem; }
  button { width: 100%; padding: 0.75rem; border: none; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; transition: background 0.2s; }
  button.primary { background: #7c6df0; color: #fff; }
  button.primary:hover { background: #6b5ce0; }
  button.primary:disabled { background: #333; color: #666; cursor: not-allowed; }
  button.download { background: #2ea043; color: #fff; margin-top: 0.75rem; }
  button.download:hover { background: #26833a; }
  #log { background: #1a1a1a; border-radius: 8px; padding: 1rem; margin-top: 1.5rem; font-family: "SF Mono", "Fira Code", monospace; font-size: 0.8rem; white-space: pre-wrap; overflow-y: auto; max-height: 300px; display: none; line-height: 1.5; }
</style>
</head>
<body>
<div class="container">
  <h1>Stem Extractor</h1>

  <div class="drop-zone" id="dropZone">
    <div>Drag &amp; drop an audio file here, or click to browse</div>
    <div class="file-name" id="fileName"></div>
    <input type="file" id="fileInput" accept="audio/*,.mp3,.wav,.flac,.ogg,.m4a,.aac,.wma">
  </div>

  <div class="settings">
    <label>
      <span>Model</span>
      <select id="model">
        <option value="htdemucs_6s">htdemucs_6s (6 stems)</option>
        <option value="htdemucs">htdemucs (4 stems)</option>
        <option value="hdemucs_mmi">hdemucs_mmi (4 stems)</option>
      </select>
    </label>
    <label>
      <span>Format</span>
      <select id="format">
        <option value="mp3">MP3</option>
        <option value="flac">FLAC</option>
      </select>
    </label>
  </div>

  <button class="primary" id="startBtn" disabled>Separate Stems</button>
  <button class="download" id="downloadBtn" style="display:none">Download ZIP</button>

  <div id="log"></div>
</div>

<script>
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileName = document.getElementById('fileName');
const startBtn = document.getElementById('startBtn');
const downloadBtn = document.getElementById('downloadBtn');
const log = document.getElementById('log');
let selectedFile = null;
let jobId = null;

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  if (e.dataTransfer.files.length) setFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', () => { if (fileInput.files.length) setFile(fileInput.files[0]); });

function setFile(f) {
  selectedFile = f;
  fileName.textContent = f.name;
  dropZone.classList.add('has-file');
  startBtn.disabled = false;
  downloadBtn.style.display = 'none';
}

startBtn.addEventListener('click', async () => {
  if (!selectedFile) return;
  startBtn.disabled = true;
  downloadBtn.style.display = 'none';
  log.style.display = 'block';
  log.textContent = 'Uploading...\\n';

  const form = new FormData();
  form.append('file', selectedFile);
  form.append('model', document.getElementById('model').value);
  form.append('format', document.getElementById('format').value);

  const res = await fetch('/upload', { method: 'POST', body: form });
  const data = await res.json();
  if (!data.job_id) { log.textContent += 'Error: ' + (data.error || 'Upload failed'); startBtn.disabled = false; return; }
  jobId = data.job_id;
  log.textContent = '';

  const evtSource = new EventSource('/stream/' + jobId);
  evtSource.onmessage = e => {
    const msg = e.data;
    if (msg === '__DONE__') {
      evtSource.close();
      downloadBtn.style.display = 'block';
      startBtn.disabled = false;
      return;
    }
    if (msg === '__ERROR__') {
      evtSource.close();
      startBtn.disabled = false;
      return;
    }
    // For tqdm-style \\r lines, replace the last line
    if (msg.startsWith('\\r') || msg.includes('\\r')) {
      const lines = log.textContent.split('\\n');
      lines[lines.length - 1] = msg.replace(/\\r/g, '');
      log.textContent = lines.join('\\n');
    } else {
      log.textContent += msg + '\\n';
    }
    log.scrollTop = log.scrollHeight;
  };
  evtSource.onerror = () => { evtSource.close(); startBtn.disabled = false; };
});

downloadBtn.addEventListener('click', () => {
  if (jobId) window.location.href = '/download/' + jobId;
});
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f:
        return jsonify(error="No file"), 400

    model = request.form.get("model", "htdemucs_6s")
    fmt = request.form.get("format", "mp3")

    if model not in ALLOWED_MODELS:
        return jsonify(error="Invalid model"), 400
    if fmt not in ALLOWED_FORMATS:
        return jsonify(error="Invalid format"), 400

    job_id = uuid.uuid4().hex[:12]
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True)

    input_path = job_dir / f.filename
    f.save(input_path)

    output_dir = job_dir / "output"
    output_dir.mkdir()

    jobs[job_id] = {
        "input_path": str(input_path),
        "output_dir": str(output_dir),
        "model": model,
        "format": fmt,
        "status": "uploaded",
    }
    return jsonify(job_id=job_id)


@app.route("/stream/<job_id>")
def stream(job_id):
    job = jobs.get(job_id)
    if not job:
        return "Not found", 404

    def generate():
        fmt_flag = "--mp3" if job["format"] == "mp3" else "--flac"
        cmd = [
            "demucs",
            fmt_flag,
            "-n", job["model"],
            "-o", job["output_dir"],
            job["input_path"],
        ]
        yield f"data: Running: {' '.join(cmd)}\n\n"

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            shell=False,
        )

        for line in proc.stdout:
            line = line.rstrip("\n")
            yield f"data: {line}\n\n"

        proc.wait()

        if proc.returncode == 0:
            job["status"] = "done"
            yield "data: __DONE__\n\n"
        else:
            job["status"] = "error"
            yield f"data: Process exited with code {proc.returncode}\n\n"
            yield "data: __ERROR__\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/download/<job_id>")
def download(job_id):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        return "Not ready", 404

    output_dir = Path(job["output_dir"])
    # demucs outputs to: output_dir / model_name / track_name / *.mp3|flac
    # Find the stem files
    stem_files = list(output_dir.rglob(f"*.{job['format']}"))
    if not stem_files:
        return "No output files found", 404

    zip_path = output_dir / "stems.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for sf in stem_files:
            zf.write(sf, sf.name)

    return send_file(zip_path, as_attachment=True, download_name="stems.zip")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
