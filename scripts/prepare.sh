# python scripts/transcribe_video.py /Users/qinminghao/Desktop/ByteDance/VideoData/raw/nanian_dongzhi/ep01/video.mp4 -o output/nanian_dongzhi_ep01
# python scripts/run_scene_detection.py /Users/qinminghao/Desktop/ByteDance/VideoData/raw/beipai_xunbao_biji/ep01/video.mp4 --video-id beipai_xunbao_biji_ep01

python scripts/run_expression_trigger_workflow_batch.py --video-id nanian_dongzhi_ep01 --force
python scripts/run_expression_trigger_workflow_batch.py --video-id beipai_xunbao_biji_ep01 --force
