import argparse
from pathlib import Path
import json
import logging
from typing import Optional
import torch
import torch.backends.mps

from .config import Config, get_client, get_model
from .frame import VideoProcessor
from .prompt import PromptLoader
from .analyzer import VideoAnalyzer
from .audio_processor import AudioProcessor, AudioTranscript
from .clients.ollama import OllamaClient
from .clients.generic_openai_api import GenericOpenAIAPIClient

# Initialize logger at module level
logger = logging.getLogger(__name__)

def write_json(path: Path, data):
    """Write JSON using UTF-8 so Chinese transcript and analysis stay readable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def append_jsonl(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

def append_frame_markdown(path: Path, frame, analysis):
    path.parent.mkdir(parents=True, exist_ok=True)
    response = analysis.get("response", "No analysis available")
    error = analysis.get("error")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"## 第 {frame.number} 帧 ({frame.timestamp:.2f}s)\n\n")
        f.write(f"- 图片路径：{frame.path}\n")
        f.write(f"- 差异评分：{frame.score:.2f}\n")
        if error:
            f.write(f"- 分析错误：{error}\n")
        f.write("\n")
        f.write(response.strip())
        f.write("\n\n")

def save_transcript_files(output_dir: Path, transcript: Optional[AudioTranscript]):
    transcript_text_path = output_dir / "transcript.txt"
    transcript_json_path = output_dir / "transcript.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    if transcript:
        transcript_text_path.write_text(transcript.text or "", encoding="utf-8")
        write_json(transcript_json_path, {
            "text": transcript.text,
            "segments": transcript.segments,
            "language": transcript.language,
        })
    else:
        transcript_text_path.write_text("", encoding="utf-8")
        write_json(transcript_json_path, {
            "text": None,
            "segments": None,
            "language": None,
        })

    return transcript_text_path, transcript_json_path

def get_log_level(level_str: str) -> int:
    """Convert string log level to logging constant."""
    levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    return levels.get(level_str.upper(), logging.INFO)

def cleanup_files(output_dir: Path):
    """Clean up temporary files and directories."""
    try:
        audio_file = output_dir / "audio.wav"
        if audio_file.exists():
            audio_file.unlink()
            logger.debug(f"Cleaned up audio file: {audio_file}")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def create_client(config: Config):
    """Create the appropriate client based on configuration."""
    client_type = config.get("clients", {}).get("default", "ollama")
    client_config = get_client(config)
    
    if client_type == "ollama":
        return OllamaClient(client_config["url"])
    elif client_type == "openai_api":
        return GenericOpenAIAPIClient(client_config["api_key"], client_config["api_url"])
    else:
        raise ValueError(f"Unknown client type: {client_type}")

def main():
    parser = argparse.ArgumentParser(description="Analyze video using Vision models")
    parser.add_argument("video_path", type=str, help="Path to the video file")
    parser.add_argument("--config", type=str, default="config",
                        help="Path to configuration directory")
    parser.add_argument("--output", type=str, help="Output directory for analysis results")
    parser.add_argument("--client", type=str, help="Client to use (ollama or openrouter)")
    parser.add_argument("--ollama-url", type=str, help="URL for the Ollama service")
    parser.add_argument("--api-key", type=str, help="API key for OpenAI-compatible service")
    parser.add_argument("--api-url", type=str, help="API URL for OpenAI-compatible API")
    parser.add_argument("--model", type=str, help="Name of the vision model to use")
    parser.add_argument("--duration", type=float, help="Duration in seconds to process")
    parser.add_argument("--keep-frames", action="store_true", help="Keep extracted frames after analysis")
    parser.add_argument("--whisper-model", type=str, help="Whisper model size (tiny, base, small, medium, large), or path to local Whisper model snapshot")
    parser.add_argument("--start-stage", type=int, default=1, help="Stage to start processing from (1-3)")
    parser.add_argument("--max-frames", type=int, default=None, help="Maximum number of frames to process")
    parser.add_argument("--log-level", type=str, default="INFO", 
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Set the logging level (default: INFO)")
    parser.add_argument("--prompt", type=str, default="",
                        help="Question to ask about the video")
    parser.add_argument("--language", type=str, default=None)
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--temperature", type=float, help="Temperature for LLM generation")
    args = parser.parse_args()

    # Set up logging with specified level
    log_level = get_log_level(args.log_level)
    # Configure the root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        force=True  # Force reconfiguration of the root logger
    )
    # Ensure our module logger has the correct level
    logger.setLevel(log_level)

    # Load and update configuration
    config = Config(args.config)
    config.update_from_args(args)

    # Initialize components
    video_path = Path(args.video_path)
    output_dir = Path(config.get("output_dir"))
    client = create_client(config)
    model = get_model(config)
    prompt_loader = PromptLoader(config.get("prompt_dir"), config.get("prompts", []))
    
    try:
        transcript = None
        frames = []
        frame_analyses = []
        fusion_result = None
        output_dir.mkdir(parents=True, exist_ok=True)
        transcript_text_path = output_dir / "transcript.txt"
        transcript_json_path = output_dir / "transcript.json"
        frame_jsonl_path = output_dir / "frame_analyses.jsonl"
        frame_md_path = output_dir / "frame_analyses.md"
        fusion_result_path = output_dir / "fusion_result.md"
        
        # Stage 1: Frame and Audio Processing
        if args.start_stage <= 1:
            # Initialize audio processor and extract transcript, the AudioProcessor accept following parameters that can be set in config.json:
            # language (str): Language code for audio transcription (default: None)
            # whisper_model (str): Whisper model size or path (default: "medium")
            # device (str): Device to use for audio processing (default: "cpu")
            logger.debug("Initializing audio processing...")
            audio_processor = AudioProcessor(language=config.get("audio", {}).get("language", ""), 
                                             model_size_or_path=config.get("audio", {}).get("whisper_model", "medium"),
                                             device=config.get("audio", {}).get("device", "cpu"))
            
            logger.info("Extracting audio from video...")
            try:
                audio_path = audio_processor.extract_audio(video_path, output_dir)
            except Exception as e:
                logger.error(f"Error extracting audio: {e}")
                audio_path = None
            
            if audio_path is None:
                logger.debug("No audio found in video - skipping transcription")
                transcript = None
            else:
                logger.info("Transcribing audio...")
                transcript = audio_processor.transcribe(audio_path)
                if transcript is None:
                    logger.warning("Could not generate reliable transcript. Proceeding with video analysis only.")

            transcript_text_path, transcript_json_path = save_transcript_files(output_dir, transcript)
            logger.info(f"Transcript files saved to {transcript_text_path} and {transcript_json_path}")
            
            logger.info(f"Extracting frames from video using model {model}...")
            processor = VideoProcessor(
                video_path, 
                output_dir / "frames", 
                model
            )
            frames = processor.extract_keyframes(
                frames_per_minute=config.get("frames", {}).get("per_minute", 60),
                duration=config.get("duration"),
                max_frames=args.max_frames
            )
            
        # Stage 2: Frame Analysis
        if args.start_stage <= 2:
            logger.info("Analyzing frames...")
            analyzer = VideoAnalyzer(
                client, 
                model, 
                prompt_loader,
                config.get("clients", {}).get("temperature", 0.2),
                config.get("prompt", "")
            )
            frame_analyses = []
            frame_jsonl_path.write_text("", encoding="utf-8")
            frame_md_path.write_text("# 逐帧画面分析\n\n", encoding="utf-8")
            for frame in frames:
                analysis = analyzer.analyze_frame(frame)
                analysis_record = {
                    "frame_number": frame.number,
                    "timestamp": frame.timestamp,
                    "image_path": str(frame.path),
                    "score": frame.score,
                    "response": analysis.get("response"),
                    "error": analysis.get("error"),
                }
                frame_analyses.append(analysis_record)
                append_jsonl(frame_jsonl_path, analysis_record)
                append_frame_markdown(frame_md_path, frame, analysis)
                logger.info(f"Saved frame {frame.number} analysis")
                
        # Stage 3: Script Fusion
        if args.start_stage <= 3:
            logger.info("Fusing frame analyses and transcript...")
            if 'analyzer' not in locals():
                analyzer = VideoAnalyzer(
                    client,
                    model,
                    prompt_loader,
                    config.get("clients", {}).get("temperature", 0.2),
                    config.get("prompt", "")
                )

            frame_analysis_text = frame_md_path.read_text(encoding="utf-8") if frame_md_path.exists() else ""
            transcript_text = transcript_text_path.read_text(encoding="utf-8") if transcript_text_path.exists() else ""
            try:
                fusion_result = analyzer.fuse_script_analysis(frame_analysis_text, transcript_text)
            except Exception as e:
                logger.error(f"Error fusing script analysis: {e}")
                fusion_result = {
                    "response": f"融合分析失败：{str(e)}",
                    "error": str(e),
                    "partial_results": [],
                    "chunk_count": 0,
                }
            fusion_result_path.write_text(fusion_result.get("response", ""), encoding="utf-8")
            logger.info(f"Fusion result saved to {fusion_result_path}")
        
        results = {
            "metadata": {
                "client": config.get("clients", {}).get("default"),
                "model": model,
                "whisper_model": config.get("audio", {}).get("whisper_model"),
                "frames_per_minute": config.get("frames", {}).get("per_minute"),
                "duration_processed": config.get("duration"),
                "frames_extracted": len(frames),
                "frames_processed": len(frame_analyses),
                "max_frames": args.max_frames,
                "start_stage": args.start_stage,
                "audio_language": transcript.language if transcript else None,
                "transcription_successful": transcript is not None
            },
            "transcript": {
                "text": transcript.text if transcript else None,
                "segments": transcript.segments if transcript else None
            } if transcript else None,
            "frame_analyses": frame_analyses,
            "fusion_result": fusion_result,
            "artifacts": {
                "transcript_txt": str(transcript_text_path),
                "transcript_json": str(transcript_json_path),
                "frame_analyses_jsonl": str(frame_jsonl_path),
                "frame_analyses_md": str(frame_md_path),
                "fusion_result_md": str(fusion_result_path),
            }
        }
        
        write_json(output_dir / "analysis.json", results)
            
        logger.info("\nTranscript:")
        if transcript:
            logger.info(transcript.text)
        else:
            logger.info("No reliable transcript available")
            
        if fusion_result:
            logger.info("\nFusion Result:")
            logger.info(fusion_result.get("response", "No fusion result generated"))
        
        if not config.get("keep_frames"):
            cleanup_files(output_dir)
        
        logger.info(f"Analysis complete. Results saved to {output_dir / 'analysis.json'}")
            
    except Exception as e:
        logger.error(f"Error during video analysis: {e}")
        if not config.get("keep_frames"):
            cleanup_files(output_dir)
        raise

if __name__ == "__main__":
    main()
