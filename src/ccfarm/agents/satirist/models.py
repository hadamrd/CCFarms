from typing import List, Optional
from ccfarm.media.audio_generator import VoiceActor
from ccfarm.media.dalle_video_gen import DalleVideoGenerator
from ccfarm.media.video_generator import ContentVideoGenerator
from moviepy import CompositeVideoClip, concatenate_videoclips
from pydantic import BaseModel, Field


class SpeechSegment(BaseModel):
    text: str = Field(
        description="The speech text content with optional SSML tags for controlling delivery. "
        "Use <emphasis>, <prosody>, and <break> tags to enhance performance and to control emotions and reactions."
    )

    keywords: List[str] = Field(
        description="Keywords that describe the emotional content and visual elements of this segment. "
        "Make sure the segment keywords are related to the subject instead of referring to random feelings or buzzwords."
    )
    
    def convert_to_video(
        self,
        elevenlabs_api_key: str,
        giphy_api_key: str,
        unsplash_api_key: str,
        output_path: Optional[str] = None,
        frame_size=(1280, 720),
        codec="libx264",
        audio_codec="libmp3lame",
        fps=24,
        audio_bitrate="192k"
    ) -> CompositeVideoClip | str | None:
        audio_generator = VoiceActor(api_key=elevenlabs_api_key)
        video_generator = ContentVideoGenerator(frame_size=frame_size)
        
        if not self.keywords:
            raise ValueError("No keywords provided for the segment")
        
        try:
            audio_segment = audio_generator.from_text(self.text)
            final_video = video_generator.from_key_words(
                keywords=self.keywords,
                giphy_api_key=giphy_api_key,
                unsplash_api_key=unsplash_api_key,
                audio_segment=audio_segment,
            )
            
            if final_video and output_path:
                final_video.write_videofile(
                    output_path,
                    codec=codec,
                    audio_codec=audio_codec,
                    fps=fps,
                    audio_bitrate=audio_bitrate
                )
                print(f"Video created successfully: {output_path}")
                return output_path
            return final_video
        except Exception as e:
            print(f"Error exporting segment to video: {str(e)}")
            return None

    def convert_to_video_dalle(
        self,
        elevenlabs_api_key: str,
        anthropic_api_key: str,
        openai_api_key: str,
        output_path: Optional[str] = None,
        frame_size=(1280, 720),
        codec="libx264",
        audio_codec="libmp3lame",
        fps=24,
        audio_bitrate="192k",
    ) -> CompositeVideoClip | str | None:
        audio_generator = VoiceActor(api_key=elevenlabs_api_key)
        video_generator = DalleVideoGenerator(
            frame_size=frame_size,
            anthropic_api_key=anthropic_api_key,
            openai_api_key=openai_api_key
        )
        
        try:
            # Generate audio from text
            audio_segment = audio_generator.from_text(self.text)
            
            # Create video from segment text and audio
            final_video = video_generator.from_text(
                text=self.text,
                audio=audio_segment,
                output_path=output_path if output_path else None
            )
            
            if final_video and output_path:
                final_video.write_videofile(
                    output_path,
                    codec=codec,
                    audio_codec=audio_codec,
                    fps=fps,
                    audio_bitrate=audio_bitrate
                )
                print(f"Video created successfully: {output_path}")
                return output_path
            return final_video
        except Exception as e:
            print(f"Error exporting segment to video: {str(e)}")
            return None

class VideoScript(BaseModel):
    title: str = Field(
        description="A catchy, satirical title for the comedy piece - should be humorous "
        "and capture the essence of the original news with an ironic twist."
    )

    description: str = Field(
        description="A brief description of the satirical take on the news article. "
        "Should explain the comedic angle in 1-2 sentences."
    )

    tags: List[str] = Field(
        description="List of relevant topics covered in the content (e.g., 'Politics', 'Technology', 'AI'). "
        "These help with content categorization and searchability."
    )

    segments: List[SpeechSegment] = Field(
        description="A series of 2-4 speech segments that form the satirical comedy piece. "
        "Each segment should be short, punchy, and include appropriate SSML tags."
    )

    def convert_to_video(
        self,
        elevenlabs_api_key: str,
        giphy_api_key: str,
        unsplash_api_key: str,
        output_path: Optional[str] = None,
        frame_size=(1280, 720),
        codec="libx264",
        audio_codec="libmp3lame",
        fps=24,
        audio_bitrate="192k"
    ):
        try:
            segment_clips = []
            for i, segment in enumerate(self.segments):
                print(f"Processing segment {i+1} of {len(self.segments)}")
                segment_clip = segment.convert_to_video(
                    elevenlabs_api_key=elevenlabs_api_key,
                    giphy_api_key=giphy_api_key,
                    unsplash_api_key=unsplash_api_key,
                    output_path=None,
                    frame_size=frame_size
                )
                if segment_clip and isinstance(segment_clip, CompositeVideoClip):
                    segment_clips.append(segment_clip)
                else:
                    print(f"Failed to create video for segment {i+1}")
            
            if not segment_clips:
                print("No segment videos were successfully created")
                return None
            
            print(f"Concatenating {len(segment_clips)} segment videos")
            final_video = concatenate_videoclips(segment_clips)
            
            if output_path:
                print(f"Writing final video to {output_path}")
                final_video.write_videofile(
                    output_path,
                    codec=codec,
                    audio_codec=audio_codec,
                    fps=fps,
                    audio_bitrate=audio_bitrate
                )
                print(f"Comedy script video created successfully: {output_path}")
                return output_path
            return final_video
        except Exception as e:
            print(f"Error creating comedy script video: {str(e)}")
            return None
    
    def convert_to_video_dalle(
        self,
        elevenlabs_api_key: str,
        anthropic_api_key: str,
        openai_api_key: str,
        output_path: Optional[str] = None,
        frame_size=(1280, 720),
        codec="libx264",
        audio_codec="libmp3lame",
        fps=24,
        audio_bitrate="192k"
    ):
        try:
            segment_clips = []
            for i, segment in enumerate(self.segments):
                print(f"Processing segment {i+1} of {len(self.segments)}")
                segment_clip = segment.convert_to_video_dalle(
                    elevenlabs_api_key=elevenlabs_api_key,
                    anthropic_api_key=anthropic_api_key,
                    openai_api_key=openai_api_key,
                    output_path=None,
                    frame_size=frame_size
                )
                if segment_clip and isinstance(segment_clip, CompositeVideoClip):
                    segment_clips.append(segment_clip)
                else:
                    print(f"Failed to create video for segment {i+1}")
            
            if not segment_clips:
                print("No segment videos were successfully created")
                return None
            
            print(f"Concatenating {len(segment_clips)} segment videos")
            final_video = concatenate_videoclips(segment_clips)
            
            if output_path:
                print(f"Writing final video to {output_path}")
                final_video.write_videofile(
                    output_path,
                    codec=codec,
                    audio_codec=audio_codec,
                    fps=fps,
                    audio_bitrate=audio_bitrate
                )
                print(f"Comedy script video created successfully: {output_path}")
                return output_path
            return final_video
        except Exception as e:
            print(f"Error creating comedy script video: {str(e)}")
            return None