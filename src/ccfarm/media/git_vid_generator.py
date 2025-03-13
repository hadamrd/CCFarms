import os
import tempfile
from typing import List, Tuple, Optional
from ccfarm.media.giphy_client import GiphyClient
from moviepy import AudioFileClip, VideoFileClip, CompositeVideoClip
from moviepy.video import fx
from pydub import AudioSegment

class GifVideoGenerator:
    """
    A class to generate video clips from GIFs without audio.
    This handles the conversion of multiple GIFs into a single composite video.
    """
    
    def __init__(self, frame_size: Tuple[int, int] = (1280, 720)):
        self.frame_size = frame_size
    
    def create_video_from_gifs(
        self, 
        gif_paths: List[str], 
        total_duration: float, 
        output_path: Optional[str] = None
    ) -> CompositeVideoClip:
        if not gif_paths:
            raise ValueError("No GIF paths provided")
            
        print(f"Creating video from {len(gif_paths)} GIFs with total duration of {total_duration:.2f} seconds")
        
        # Calculate duration for each GIF
        gif_duration = total_duration / len(gif_paths)
        print(f"Each GIF will play for {gif_duration:.2f} seconds")
        
        # Create video clips from GIFs
        video_clips = []
        start_time = 0.0
        
        for gif_path in gif_paths:
            print(f"Processing GIF: {os.path.basename(gif_path)}")
            gif_clip = VideoFileClip(gif_path, has_mask=False)
            
            # Handle static or short GIFs by looping to match duration
            gif_clip = gif_clip.with_effects([fx.Loop(duration=gif_duration)])
            
            # Resize to height of frame, maintaining aspect ratio
            resized_clip = gif_clip.resized(height=self.frame_size[1]) # type: ignore
            
            # Center the clip horizontally
            w, h = resized_clip.size # type: ignore
            pos = ((self.frame_size[0] - w) / 2, (self.frame_size[1] - h) / 2)
            positioned_clip = resized_clip.with_position(pos).with_start(start_time) # type: ignore
            
            video_clips.append(positioned_clip)
            start_time += gif_duration

        if not video_clips:
            raise ValueError("No valid video clips could be created from the GIFs")
        
        # Create composite video
        composite_video = CompositeVideoClip(video_clips, size=self.frame_size)
        
        # Save to file if output path is provided
        if output_path:
            try:
                composite_video.write_videofile(
                    output_path,
                    codec="libx264",
                    fps=24
                )
                print(f"Silent video created successfully: {output_path}")
            except Exception as e:
                print(f"Error saving video to {output_path}: {str(e)}")
        
        return composite_video
    
    def create_video_segment(
        self, 
        keywords: List[str], 
        giphy_api_key: str,
        duration: float, 
        temp_dir: str
    ) -> Optional[CompositeVideoClip]:
        giphy_client = GiphyClient(api_key=giphy_api_key)
        # Download GIFs for each keyword
        gif_paths = []
        
        for i, keyword in enumerate(keywords):
            # Search for GIF
            gifs_data = giphy_client.search_gif(keyword, limit=3)
            if gifs_data and len(gifs_data) > 0:
                # Use first GIF URL
                for gif_data in gifs_data:
                    gif_path = os.path.join(temp_dir, f"keyword_{i}.gif")
                    
                    # Download GIF
                    if giphy_client.download_gif(gif_data, gif_path):
                        gif_paths.append(gif_path)
                    else:
                        raise Exception(f"Failed to download GIF for keyword '{keyword}'")
            else:
                raise Exception(f"No GIF found for keyword '{keyword}'")
        
        # Create video from GIFs
        return self.create_video_from_gifs(gif_paths, duration)

    def from_key_words(
        self,
        keywords: List[str],
        giphy_api_key: str,
        audio_segment: AudioSegment,
    ) -> Optional[CompositeVideoClip]:
        # Save audio to temporary file
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_audio_path = os.path.join(temp_dir, "temp_audio.mp3")
            audio_segment.export(temp_audio_path, format="mp3")
            
            # Convert to MoviePy AudioFileClip
            audio_clip = AudioFileClip(temp_audio_path)
            
            # Create silent video from GIFs
            silent_video = self.create_video_segment(
                keywords=keywords,
                giphy_api_key=giphy_api_key,
                duration=audio_clip.duration,
                temp_dir=temp_dir
            )
            
            if not silent_video:
                return None
            
            # Add audio to video
            final_video = silent_video.with_audio(audio_clip)
            return final_video
    