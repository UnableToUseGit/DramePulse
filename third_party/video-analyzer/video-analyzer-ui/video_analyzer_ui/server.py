#!/usr/bin/env python3
import argparse
import logging
import os
import re
import subprocess
import sys
import unicodedata
import uuid
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, Response
from werkzeug.utils import secure_filename

# Initialize logger
logger = logging.getLogger(__name__)

class VideoAnalyzerUI:
    def __init__(self, host='localhost', port=5000, dev_mode=False):
        self.app = Flask(__name__)
        self.host = host
        self.port = port
        self.dev_mode = dev_mode
        self.sessions = {}
        
        # Keep UI uploads/results inside the project directory instead of the
        # system temp directory so analysis artifacts are easy to inspect.
        self.project_root = Path(__file__).resolve().parents[2]
        self.data_root = self.project_root / 'ui_data'
        self.uploads_dir = self.data_root / 'uploads'
        self.results_dir = self.data_root / 'results'
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        self.setup_routes()

    def _redact_command(self, cmd):
        """Return a command string with sensitive argument values hidden."""
        redacted = []
        hide_next = False
        for part in cmd:
            if hide_next:
                redacted.append("***")
                hide_next = False
                continue

            redacted.append(part)
            if part in {"--api-key"}:
                hide_next = True

        return " ".join(redacted)

    def _safe_dir_part(self, value, fallback):
        value = (value or "").strip()
        if not value:
            value = fallback
        value = unicodedata.normalize("NFKD", value)
        value = value.encode("ascii", "ignore").decode("ascii")
        value = value.lower()
        value = re.sub(r'[^a-z0-9]+', '_', value)
        value = value.strip('_')
        return value[:80] or fallback

    def _build_session_name(self, filename):
        raw_series_name = request.form.get('series_name') or Path(filename).stem
        raw_episode = request.form.get('episode') or '1'
        try:
            episode = max(1, int(raw_episode))
        except (TypeError, ValueError):
            episode = 1

        series_name = self._safe_dir_part(raw_series_name, 'drama')
        suffix = uuid.uuid4().hex[:8]
        session_name = f"{series_name}_ep{episode:03d}_{suffix}"
        display_name = f"{raw_series_name.strip() or series_name} 第{episode}集"
        return session_name, display_name, episode
        
    def setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template('index.html')
            
        @self.app.route('/upload', methods=['POST'])
        def upload_file():
            if 'video' not in request.files:
                return jsonify({'error': 'No video file provided'}), 400
                
            file = request.files['video']
            if file.filename == '':
                return jsonify({'error': 'No selected file'}), 400
                
            if not file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                return jsonify({'error': 'Invalid file type'}), 400
                
            try:
                # Create session
                filename = secure_filename(file.filename)
                session_id, display_name, episode = self._build_session_name(filename)
                session_upload_dir = self.uploads_dir / session_id
                session_results_dir = self.results_dir / session_id
                session_upload_dir.mkdir(parents=True)
                session_results_dir.mkdir(parents=True)
                
                # Save file
                filepath = session_upload_dir / filename
                file.save(filepath)
                
                self.sessions[session_id] = {
                    'video_path': str(filepath),
                    'results_dir': str(session_results_dir),
                    'filename': filename,
                    'series_name': display_name,
                    'episode': episode,
                    'display_name': display_name
                }
                
                return jsonify({
                    'session_id': session_id,
                    'display_name': display_name,
                    'message': 'File uploaded successfully'
                })
                
            except Exception as e:
                logger.error(f"Upload error: {e}")
                return jsonify({'error': str(e)}), 500
                
        @self.app.route('/analyze/<session_id>', methods=['POST'])
        def analyze(session_id):
            if session_id not in self.sessions:
                return jsonify({'error': 'Invalid session'}), 404
                
            session = self.sessions[session_id]
            
            # Build command
            cmd = ['video-analyzer', session['video_path']]
            
            # Add optional parameters
            for param, value in request.form.items():
                if value:  # Only add parameters with values
                    if param in ['keep-frames', 'dev']:  # Flags without values
                        cmd.append(f'--{param}')
                    else:
                        cmd.extend([f'--{param}', value])
                        
            # Create output directory if it doesn't exist
            results_dir = Path(session['results_dir'])
            results_dir.mkdir(parents=True, exist_ok=True)
            
            # Add output directory
            cmd.extend(['--output', str(results_dir)])
            
            # Store output directory in session for later use
            session['output_dir'] = str(results_dir)
            logger.debug(f"Set output directory to: {results_dir}")
            
            # Store command in session for streaming
            session['cmd'] = cmd
            session['log_file'] = str(results_dir / 'analysis.log')
            
            return jsonify({'message': 'Analysis started'})
            
        @self.app.route('/analyze/<session_id>/stream')
        def stream_output(session_id):
            if session_id not in self.sessions:
                return jsonify({'error': 'Invalid session'}), 404
                
            session = self.sessions[session_id]
            if 'cmd' not in session:
                return jsonify({'error': 'Analysis not started'}), 400
                
            def generate_output():
                log_file = Path(session.get('log_file', Path(session['results_dir']) / 'analysis.log'))
                redacted_command = self._redact_command(session['cmd'])
                logger.debug(f"Starting analysis with command: {redacted_command}")
                try:
                    with log_file.open('w', encoding='utf-8') as log:
                        log.write(f"Command: {redacted_command}\n\n")
                        log.flush()

                        env = os.environ.copy()
                        env["PYTHONIOENCODING"] = "utf-8"
                        env["PYTHONUTF8"] = "1"

                        process = subprocess.Popen(
                            session['cmd'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            env=env,
                            bufsize=1
                        )

                        for raw_line in process.stdout:
                            log.write(raw_line)
                            log.flush()

                            line = raw_line.strip()
                            if line:  # Only send non-empty lines
                                logger.debug(f"Output: {line}")
                                yield f"data: {line}\n\n"

                        process.wait()
                        if process.returncode == 0:
                            message = "Analysis completed successfully"
                            logger.info(message)
                            log.write(f"{message}\n")
                            yield f"data: {message}\n\n"
                        else:
                            message = f"Analysis failed with code {process.returncode}"
                            logger.error(message)
                            log.write(f"{message}\n")
                            yield f"data: {message}\n\n"
                except Exception as e:
                    message = f"Error during analysis: {str(e)}"
                    logger.error(message)
                    try:
                        with log_file.open('a', encoding='utf-8') as log:
                            log.write(f"{message}\n")
                            log.write("Analysis failed\n")
                    except Exception as log_error:
                        logger.error(f"Error writing analysis log: {log_error}")

                    yield f"data: {message}\n\n"
                    yield f"data: Analysis failed\n\n"
                    
            return Response(
                generate_output(),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive'
                }
            )
            
        @self.app.route('/results/<session_id>')
        def get_results(session_id):
            if session_id not in self.sessions:
                return jsonify({'error': 'Invalid session'}), 404
                
            session = self.sessions[session_id]
            results_dir = Path(session['results_dir'])
            logger.debug(f"Looking for results in: {results_dir}")
            
            if not results_dir.exists():
                logger.error(f"Results directory not found: {results_dir}")
                return jsonify({'error': 'Results directory not found'}), 404
            
            # List all files in results directory for debugging
            logger.debug("Files in results directory:")
            for file in results_dir.glob('**/*'):
                logger.debug(f"- {file}")
            
            # Check both the results directory and the default 'output' directory
            analysis_file = results_dir / 'analysis.json'
            default_output = Path('output/analysis.json')
            
            if default_output.exists():
                logger.debug(f"Found analysis file in default output directory: {default_output}")
                try:
                    # Move the file to our results directory
                    default_output.rename(analysis_file)
                    logger.debug(f"Moved analysis file to: {analysis_file}")
                except Exception as e:
                    logger.error(f"Error moving analysis file: {e}")
                    # If move fails, try to copy the content
                    try:
                        analysis_file.write_text(default_output.read_text())
                        logger.debug("Copied analysis file content")
                        default_output.unlink()
                    except Exception as copy_error:
                        logger.error(f"Error copying analysis file: {copy_error}")
                        return jsonify({'error': 'Error accessing analysis file'}), 500
            if not analysis_file.exists():
                logger.error(f"Analysis file not found: {analysis_file}")
                return jsonify({'error': 'Analysis file not found'}), 404
                
            try:
                return send_file(
                    analysis_file,
                    mimetype='application/json',
                    as_attachment=True,
                    download_name=f"analysis_{session['filename']}.json"
                )
            except Exception as e:
                logger.error(f"Error sending file: {e}")
                return jsonify({'error': f'Error sending file: {str(e)}'}), 500

        @self.app.route('/logs/<session_id>')
        def get_logs(session_id):
            if session_id not in self.sessions:
                return jsonify({'error': 'Invalid session'}), 404

            session = self.sessions[session_id]
            log_file = Path(session.get('log_file', Path(session['results_dir']) / 'analysis.log'))

            if not log_file.exists():
                return jsonify({'error': 'Analysis log not found'}), 404

            try:
                return send_file(
                    log_file,
                    mimetype='text/plain',
                    as_attachment=True,
                    download_name=f"analysis_{session['filename']}.log"
                )
            except Exception as e:
                logger.error(f"Error sending log file: {e}")
                return jsonify({'error': f'Error sending log file: {str(e)}'}), 500
            
        @self.app.route('/cleanup/<session_id>', methods=['POST'])
        def cleanup_session(session_id):
            if session_id not in self.sessions:
                return jsonify({'error': 'Invalid session'}), 404
                
            try:
                del self.sessions[session_id]
                return jsonify({'message': 'Session removed. Files were kept on disk.'})
                
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
                return jsonify({'error': str(e)}), 500
    
    def run(self):
        self.app.run(
            host=self.host,
            port=self.port,
            debug=self.dev_mode
        )

def main():
    parser = argparse.ArgumentParser(description="Video Analyzer UI Server")
    parser.add_argument('--host', default='localhost', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to listen on')
    parser.add_argument('--dev', action='store_true', help='Enable development mode')
    parser.add_argument('--log-file', help='Log file path')
    
    args = parser.parse_args()
    
    # Configure logging
    log_config = {
        'level': logging.DEBUG if args.dev else logging.INFO,
        'format': '%(asctime)s - %(levelname)s - %(message)s',
    }
    if args.log_file:
        log_config['filename'] = args.log_file
    logging.basicConfig(**log_config)
    
    try:
        # Check if video-analyzer is installed
        subprocess.run(['video-analyzer', '--help'], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        logger.error("video-analyzer command not found. Please install video-analyzer package.")
        sys.exit(1)
    except FileNotFoundError:
        logger.error("video-analyzer command not found. Please install video-analyzer package.")
        sys.exit(1)
    
    # Start server
    server = VideoAnalyzerUI(
        host=args.host,
        port=args.port,
        dev_mode=args.dev
    )
    server.run()

if __name__ == '__main__':
    main()
