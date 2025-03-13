import os
import json
import glob
from moviepy import VideoFileClip, concatenate_videoclips, AudioFileClip
from moviepy.video import fx 
import sys
import re

def create_segment_video(segment_data, segment_index, output_dir, gifs_dir):
    """Create a video for a single segment using its audio and related GIFs."""
    segment_number = segment_index + 1
    print(f"\n=== Creating video for segment {segment_number} ===")
    
    # Get segment details
    filename = segment_data.get("filename")
    duration = segment_data.get("duration")
    keywords = segment_data.get("keywords", [])
    
    print(f"Segment audio: {filename}")
    print(f"Duration: {duration} seconds")
    print(f"Keywords: {keywords}")
    
    # Find audio file
    audio_path = os.path.join(output_dir, filename)
    if not os.path.exists(audio_path):
        print(f"Error: Audio file not found at {audio_path}")
        return None
    
    # Find related GIFs for this segment
    segment_pattern = f"segment{segment_number:02d}_keyword*.gif"
    segment_gifs = glob.glob(os.path.join(gifs_dir, segment_pattern))
    
    # If no segment-specific GIFs found, try the older naming convention
    if not segment_gifs:
        # Try to find GIFs with the old naming pattern (combined keywords)
        keywords_slug = "_".join(keywords).lower().replace(" ", "_")
        old_pattern = f"{segment_number:02d}_{keywords_slug}.gif"
        segment_gifs = glob.glob(os.path.join(gifs_dir, old_pattern))
    
    if not segment_gifs:
        print(f"No GIFs found for segment {segment_number}")
        return None
    
    print(f"Found {len(segment_gifs)} GIFs for segment {segment_number}")
    
    # Calculate duration for each GIF
    gif_duration = duration / len(segment_gifs)
    print(f"Each GIF will play for {gif_duration:.2f} seconds")
    
    # Create video clips from GIFs
    video_clips = []
    for gif_path in sorted(segment_gifs):  # Sort to ensure consistent order
        try:
            print(f"Processing GIF: {os.path.basename(gif_path)}")
            gif_clip = VideoFileClip(gif_path)
            
            # Loop the GIF for its allocated duration
            looped_clip = gif_clip.with_effects([fx.Loop(duration=gif_duration)])
            
            # Resize to standard dimensions (maintaining aspect ratio)
            resized_clip = looped_clip.resized(height=720)
            
            video_clips.append(resized_clip)
        except Exception as e:
            print(f"Error processing GIF {gif_path}: {str(e)}")
    
    if not video_clips:
        print(f"No valid video clips created for segment {segment_number}")
        return None
    
    # Create segment video and audio separately, then combine them
    try:
        print("Concatenating GIF clips...")
        segment_video = concatenate_videoclips(video_clips)
        
        print(f"Segment video duration: {segment_video.duration:.2f} seconds")
        print(f"Expected audio duration: {duration} seconds")
        
        # Ensure video duration matches expected audio duration
        if abs(segment_video.duration - duration) > 0.1:
            print(f"Adjusting video duration to match audio ({duration:.2f} seconds)")
            segment_video = segment_video.with_duration(duration)
        
        # Save segment video first without audio
        temp_filename = f"temp_segment_{segment_number:02d}.mp4"
        temp_path = os.path.join(output_dir, "segment_videos", temp_filename)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        
        print(f"Writing video without audio to: {temp_path}")
        segment_video.write_videofile(temp_path, codec='libx264', audio=False)
        
        # Now create the final video with audio
        segment_video_filename = f"segment_{segment_number:02d}.mp4"
        segment_video_path = os.path.join(output_dir, "segment_videos", segment_video_filename)
        
        print(f"Adding audio from {audio_path} to video...")
        
        # Use ffmpeg directly via a system command for more reliable audio addition
        import subprocess
        cmd = [
            'ffmpeg',
            '-i', temp_path,                # Input video (without audio)
            '-i', audio_path,               # Input audio
            '-c:v', 'copy',                # Copy video stream without re-encoding
            '-c:a', 'aac',                 # Audio codec
            '-b:a', '192k',                # Audio bitrate
            '-shortest',                   # Match duration of shortest input
            '-y',                          # Overwrite output if exists
            segment_video_path             # Output file
        ]
        
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error running ffmpeg: {result.stderr}")
            return None
        
        # Clean up temporary file
        try:
            os.remove(temp_path)
        except:
            pass
        
        # Verify the created file has audio
        if os.path.exists(segment_video_path) and os.path.getsize(segment_video_path) > 0:
            print(f"Segment {segment_number} video created successfully")
            return segment_video_path
        else:
            print(f"Failed to create segment video or file is empty")
            return None
    
    except Exception as e:
        print(f"Error creating segment {segment_number} video: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def create_segment_videos(output_dir):
    """Create individual videos for each segment in the metadata."""
    # Find metadata file
    metadata_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
    if not metadata_files:
        print(f"No metadata file found in {output_dir}")
        return []
    
    metadata_path = metadata_files[0]
    print(f"Using metadata file: {metadata_path}")
    
    # Load metadata
    try:
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
    except Exception as e:
        print(f"Error loading metadata: {str(e)}")
        return []
    
    # Get segments
    segments = metadata.get("segments", [])
    if not segments:
        print("No segments found in metadata")
        return []
    
    print(f"Found {len(segments)} segments in metadata")
    
    # Find GIFs directory
    gifs_dir = os.path.join(output_dir, "gifs")
    if not os.path.exists(gifs_dir):
        print(f"GIFs directory not found at {gifs_dir}")
        return []
    
    # Create segment videos
    segment_videos = []
    for i, segment in enumerate(segments):
        segment_video_path = create_segment_video(segment, i, output_dir, gifs_dir)
        if segment_video_path:
            segment_videos.append(segment_video_path)
    
    print(f"\n=== Segment video creation complete ===")
    print(f"Created {len(segment_videos)} segment videos out of {len(segments)} segments")
    
    return segment_videos

def combine_segment_videos(segment_videos, output_dir, metadata_path=None):
    """Combine all segment videos into a final video."""
    if not segment_videos:
        print("No segment videos to combine")
        return None
    
    print(f"\n=== Combining {len(segment_videos)} segment videos ===")
    
    # Load metadata for title if available
    title = "combined_video"
    if metadata_path and os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            title = metadata.get("title", "combined_video")
        except:
            pass
    
    safe_title = re.sub(r'[^\w\-_\. ]', '_', title).replace(' ', '_')
    combined_video_path = os.path.join(output_dir, f"{safe_title}_combined.mp4")
    
    # Use ffmpeg to concatenate videos (preserves audio better than MoviePy)
    try:
        # Create a temporary file listing all input videos
        list_file_path = os.path.join(output_dir, "segment_videos", "segments_list.txt")
        with open(list_file_path, 'w') as f:
            for video_path in sorted(segment_videos):
                f.write(f"file '{os.path.abspath(video_path)}'\n")
        
        import subprocess
        cmd = [
            'ffmpeg',
            '-f', 'concat',              # Use concat demuxer
            '-safe', '0',                # Don't be strict about the concat syntax
            '-i', list_file_path,        # Input file list
            '-c', 'copy',                # Copy streams without re-encoding
            '-y',                        # Overwrite output if exists
            combined_video_path          # Output file
        ]
        
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Clean up list file
        try:
            os.remove(list_file_path)
        except:
            pass
        
        if result.returncode != 0:
            print(f"Error running ffmpeg: {result.stderr}")
            return None
        
        print(f"Combined video created successfully at: {combined_video_path}")
        return combined_video_path
    
    except Exception as e:
        print(f"Error creating combined video: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def main():
    # Get output directory from command line arguments
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        # Default path as requested
        output_dir = "/home/kmajdoub/orchestration-play/output"
    
    if not os.path.exists(output_dir):
        print(f"Error: Output directory not found at {output_dir}")
        return
    
    print(f"Processing output directory: {output_dir}")
    
    # Create individual segment videos
    segment_videos = create_segment_videos(output_dir)
    
    # Combine segment videos
    if segment_videos and len(segment_videos) > 1:
        combine_option = input("Do you want to combine all segment videos into one? (y/n): ").lower()
        if combine_option.startswith('y'):
            metadata_path = glob.glob(os.path.join(output_dir, "*_metadata.json"))
            metadata_path = metadata_path[0] if metadata_path else None
            combine_segment_videos(segment_videos, output_dir, metadata_path)
    elif segment_videos:
        print("Only one segment video created, not combining.")
    
    print("\nProcessing complete!")

if __name__ == "__main__":
    main()