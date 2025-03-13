import subprocess

# Paths
audio_path = "/home/kmajdoub/orchestration-play/output/audios/segment01.mp3"
output_path = "ffmpeg_direct_black.mp4"

# Direct FFmpeg command to create black video with audio
cmd = [
    'ffmpeg',
    '-f', 'lavfi', 
    '-i', 'color=c=black:s=1280x720:r=24:d=13.82',  # Create black frame with correct duration
    '-i', audio_path,
    '-c:v', 'libx264',
    '-tune', 'stillimage',
    '-c:a', 'aac',
    '-b:a', '256k',  # Higher bitrate for audio
    '-shortest',
    '-y',
    output_path
]

# Run the command
subprocess.run(cmd)