from typing import List, Dict, Any, Optional
import logging
from .clients.llm_client import LLMClient
from .prompt import PromptLoader
from .frame import Frame
from .audio_processor import AudioTranscript

logger = logging.getLogger(__name__)

MAX_FUSION_INPUT_CHARS = 24000
MAX_TRANSCRIPT_CHARS_PER_FUSION = 8000

class VideoAnalyzer:
    def __init__(self, client: LLMClient, model: str, prompt_loader: PromptLoader, temperature: float, user_prompt: str = ""):
        """Initialize the VideoAnalyzer.
        
        Args:
            client: LLM client for making API calls
            model: Name of the model to use
            prompt_loader: Loader for prompt templates
            user_prompt: Optional user question about the video that will be injected into frame analysis
                        and video description prompts using the {prompt} token
        """
        self.client = client
        self.model = model
        self.prompt_loader = prompt_loader
        self.temperature = temperature
        self.user_prompt = user_prompt  # Store user's question about the video
        self._load_prompts()
        
    def _format_user_prompt(self) -> str:
        """Format the user's prompt by adding prefix if not empty."""
        if self.user_prompt:
            return f"I want to know {self.user_prompt}"
        return ""
        
    def _load_prompts(self):
        """Load prompts from files."""
        self.frame_prompt = self.prompt_loader.get_by_index(0)  # Frame Analysis prompt
        self.video_prompt = self.prompt_loader.get_by_index(1)  # Video Reconstruction prompt

    def analyze_frame(self, frame: Frame) -> Dict[str, Any]:
        """Analyze a single frame using the LLM."""
        # Analyze each frame independently so long videos do not accumulate prompt context.
        prompt = self.frame_prompt.replace("{PREVIOUS_FRAMES}", "")
        prompt = prompt.replace("{prompt}", self._format_user_prompt())
        prompt = f"{prompt}\nThis is frame {frame.number} captured at {frame.timestamp:.2f} seconds."
        
        try:
            response = self.client.generate(
                prompt=prompt,
                image_path=str(frame.path),
                model=self.model,
                temperature=self.temperature,
                num_predict=300
            )
            logger.debug(f"Successfully analyzed frame {frame.number}")
            
            analysis_result = {k: v for k, v in response.items() if k != "context"}
            return analysis_result
        except Exception as e:
            logger.error(f"Error analyzing frame {frame.number}: {e}")
            return {
                "response": f"Error analyzing frame {frame.number}: {str(e)}",
                "error": str(e),
            }

    def _build_fusion_prompt(self, frame_notes: str, transcript_text: str, title: str) -> str:
        """Build a script-fusion prompt from frame notes and transcript text."""
        prompt = self.video_prompt.replace("{prompt}", self._format_user_prompt())
        prompt = prompt.replace("{FRAME_NOTES}", frame_notes)
        prompt = prompt.replace("{FIRST_FRAME}", "")
        prompt = prompt.replace("{TRANSCRIPT}", transcript_text)
        return (
            f"{prompt}\n\n"
            f"当前融合任务：{title}\n"
            "请只输出简体中文，不要输出英文说明。"
        )

    def _split_text(self, text: str, max_chars: int) -> List[str]:
        """Split text into chunks at line boundaries when possible."""
        if len(text) <= max_chars:
            return [text]

        chunks = []
        current = []
        current_len = 0
        for line in text.splitlines(keepends=True):
            if current and current_len + len(line) > max_chars:
                chunks.append("".join(current).strip())
                current = []
                current_len = 0
            current.append(line)
            current_len += len(line)

        if current:
            chunks.append("".join(current).strip())

        return [chunk for chunk in chunks if chunk]

    def fuse_script_analysis(self, frame_analysis_text: str, transcript_text: str) -> Dict[str, Any]:
        """Fuse frame notes and transcript into a Chinese short-drama script analysis."""
        transcript_for_prompt = transcript_text.strip()
        if len(transcript_for_prompt) > MAX_TRANSCRIPT_CHARS_PER_FUSION:
            transcript_for_prompt = (
                transcript_for_prompt[:MAX_TRANSCRIPT_CHARS_PER_FUSION]
                + "\n\n[台词内容过长，以上为前段节选。完整台词已保存到 transcript.txt。]"
            )

        frame_chunks = self._split_text(frame_analysis_text.strip(), MAX_FUSION_INPUT_CHARS)
        if not frame_chunks:
            frame_chunks = ["[无可用画面分析。]"]

        partial_results = []
        for idx, chunk in enumerate(frame_chunks, start=1):
            title = f"第 {idx}/{len(frame_chunks)} 段画面分析与台词融合"
            response = self.client.generate(
                prompt=self._build_fusion_prompt(chunk, transcript_for_prompt, title),
                model=self.model,
                temperature=self.temperature,
                num_predict=1500,
            )
            partial_results.append(response.get("response", ""))

        if len(partial_results) == 1:
            return {
                "response": partial_results[0],
                "partial_results": partial_results,
                "chunk_count": 1,
            }

        merge_prompt = (
            "你是短剧剧本分析助手。下面是按时间顺序得到的多个分段分析结果。\n"
            "请融合为一份完整、去重、连贯的简体中文短剧结构分析。\n"
            "必须包含：整体概述、主要人物、人物关系、分场景剧情、关键对白、冲突转折、结论。\n\n"
            + "\n\n".join(
                f"## 分段结果 {idx}\n{result}"
                for idx, result in enumerate(partial_results, start=1)
            )
        )
        final_response = self.client.generate(
            prompt=merge_prompt,
            model=self.model,
            temperature=self.temperature,
            num_predict=1800,
        )
        return {
            "response": final_response.get("response", ""),
            "partial_results": partial_results,
            "chunk_count": len(partial_results),
        }

    def reconstruct_video(self, frame_analyses: List[Dict[str, Any]], frames: List[Frame], 
                         transcript: Optional[AudioTranscript] = None) -> Dict[str, Any]:
        """Reconstruct video description from frame analyses and transcript."""
        frame_notes = []
        for i, (frame, analysis) in enumerate(zip(frames, frame_analyses)):
            frame_note = (
                f"Frame {i} ({frame.timestamp:.2f}s):\n"
                f"{analysis.get('response', 'No analysis available')}"
            )
            frame_notes.append(frame_note)
        
        analysis_text = "\n\n".join(frame_notes)
        
        # Get first frame analysis
        first_frame_text = ""
        if frame_analyses and len(frame_analyses) > 0:
            first_frame_text = frame_analyses[0].get('response', '')
        
        # Include transcript information if available
        transcript_text = ""
        if transcript and transcript.text.strip():
            transcript_text = transcript.text
        
        # Replace tokens in the prompt template
        prompt = self.video_prompt.replace("{prompt}", self._format_user_prompt())
        prompt = prompt.replace("{FRAME_NOTES}", analysis_text)
        prompt = prompt.replace("{FIRST_FRAME}", first_frame_text)
        prompt = prompt.replace("{TRANSCRIPT}", transcript_text)
        
        try:
            response = self.client.generate(
                prompt=prompt,
                model=self.model,
                temperature=self.temperature,
                num_predict=1000
            )
            logger.info("Successfully reconstructed video description")
            return {k: v for k, v in response.items() if k != "context"}
        except Exception as e:
            logger.error(f"Error reconstructing video: {e}")
            return {"response": f"Error reconstructing video: {str(e)}"}
