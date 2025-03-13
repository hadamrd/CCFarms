import os
import tempfile
from typing import List, Tuple, Optional
from ccfarm.media.giphy_client import GiphyClient
from ccfarm.media.unsplash_client import UnsplashClient
from moviepy import AudioFileClip, ImageClip, VideoFileClip, CompositeVideoClip
from moviepy.video import fx
from pydub import AudioSegment

class ContentVideoGenerator:
    """
    A class to generate video clips from GIFs without audio.
    This handles the conversion of multiple GIFs into a single composite video.
    """
    
    def __init__(self, frame_size: Tuple[int, int] = (1280, 720)):
        self.frame_size = frame_size
    
    def create_video_from_visuals(
        self,
        visual_paths: List[str],
        total_duration: float,
        output_path: Optional[str] = None
    ) -> CompositeVideoClip:
        if not visual_paths:
            raise ValueError("No visual paths provided")

        print(f"Creating video from {len(visual_paths)} visuals with total duration of {total_duration:.2f} seconds")
        
        # Calculate duration for each visual
        visual_duration = total_duration / len(visual_paths)
        print(f"Each visual will play for {visual_duration:.2f} seconds")
        
        video_clips = []
        start_time = 0.0
        
        for path in visual_paths:
            print(f"Processing visual: {os.path.basename(path)}")
            if path.lower().endswith('.gif'):
                clip = VideoFileClip(path)
                clip = clip.with_effects([fx.Loop(duration=visual_duration)])
            else:  # Assume it's an image (e.g., .jpg, .png)
                clip = ImageClip(path, duration=visual_duration)
            
            # Resize to frame height, maintaining aspect ratio
            clip = clip.resized(height=self.frame_size[1])  # type: ignore
            
            # Center the clip horizontally
            w, h = clip.size  # type: ignore
            pos = ((self.frame_size[0] - w) / 2, (self.frame_size[1] - h) / 2)
            positioned_clip = clip.with_position(pos).with_start(start_time)  # type: ignore
            
            video_clips.append(positioned_clip)
            start_time += visual_duration

        if not video_clips:
            raise ValueError("No valid video clips could be created from the visuals")
        
        composite_video = CompositeVideoClip(video_clips, size=self.frame_size)
        
        if output_path:
            composite_video.write_videofile(output_path, codec="libx264", fps=24)
        
        return composite_video
    
    def from_key_words(
        self,
        keywords: List[str],
        giphy_api_key: str,
        unsplash_api_key: str,  # New parameter
        audio_segment: AudioSegment,
    ) -> Optional[CompositeVideoClip]:
        with tempfile.TemporaryDirectory() as temp_dir:
            visual_paths = []
            
            giphy_client = GiphyClient(api_key=giphy_api_key)
            unsplash_client = UnsplashClient(api_key=unsplash_api_key)
            
            for keyword in keywords:
                # Fetch GIF
                gifs_data = giphy_client.search_gif(keyword, limit=1)
                if gifs_data and len(gifs_data) > 0:
                    gif_path = os.path.join(temp_dir, f"{keyword}_gif.gif")
                    if giphy_client.download_gif(gifs_data[0], gif_path):
                        visual_paths.append(gif_path)
                    else:
                        print(f"Failed to download GIF for '{keyword}'")
                
                # Fetch Image
                images_data = unsplash_client.search_image(keyword, limit=1)
                if images_data and len(images_data) > 0:
                    image_path = os.path.join(temp_dir, f"{keyword}_image.jpg")
                    if unsplash_client.download_image(images_data[0], image_path):
                        visual_paths.append(image_path)
                    else:
                        print(f"Failed to download image for '{keyword}'")
            
            if not visual_paths:
                print("No visuals could be fetched")
                return None
            
            # Save audio
            temp_audio_path = os.path.join(temp_dir, "temp_audio.mp3")
            audio_segment.export(temp_audio_path, format="mp3")
            audio_clip = AudioFileClip(temp_audio_path)
            
            # Create silent video
            silent_video = self.create_video_from_visuals(
                visual_paths=visual_paths,
                total_duration=audio_clip.duration
            )
            
            # Add audio
            final_video = silent_video.with_audio(audio_clip)
            return final_video
        