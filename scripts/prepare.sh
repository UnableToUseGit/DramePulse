# python scripts/transcribe_video.py /Users/qinminghao/Desktop/ByteDance/VideoData/raw/nanian_dongzhi/ep01/video.mp4 -o output/nanian_dongzhi_ep01
# python scripts/run_scene_detection.py /Users/qinminghao/Desktop/ByteDance/VideoData/raw/beipai_xunbao_biji/ep01/video.mp4 --video-id beipai_xunbao_biji_ep01

python scripts/run_highlight_candidate_generation.py nanian_dongzhi_ep01 --transcription output/nanian_dongzhi_ep01/video.transcription.json --scene-detection output/nanian_dongzhi_ep01/scene_detection.json
python scripts/run_highlight_candidate_generation.py beipai_xunbao_biji_ep01 --transcription output/beipai_xunbao_biji_ep01/video.transcription.json --scene-detection output/beipai_xunbao_biji_ep01/scene_detection.json