import os
import tempfile
from typing import List, Optional
from ccfarm.media.audio_generator import VoiceActor
from ccfarm.media.giphy_client import GiphyClient
from ccfarm.media.git_vid_generator import GifVideoGenerator
from moviepy import CompositeVideoClip, concatenate_videoclips
from pydantic import BaseModel, Field


class SpeechSegment(BaseModel):
    text: str = Field(
        description="The speech text content with optional SSML tags for controlling delivery. "
        "Use <emphasis>, <prosody>, and <break> tags to enhance performance and to control emotions and reactions."
    )

    keywords: List[str] = Field(
        description="Keywords that describe the emotional content and visual elements of this segment. "
        "These will be used to fetch matching GIFs. Examples: 'shocked', 'facepalm', "
        "'eye-roll', 'sarcastic', etc. Choose 5-8 descriptive terms per segment."
    )
    
    def convert_to_video(
        self,
        elevenlabs_api_key: str,
        giphy_api_key: str,
        output_path: str|None=None,
        frame_size=(1280, 720),
        codec="libx264",
        audio_codec="libmp3lame",
        fps=24,
        audio_bitrate="192k"
    ) -> Optional[str]|CompositeVideoClip:
        # Initialize the components
        audio_generator = VoiceActor(api_key=elevenlabs_api_key)
        video_generator = GifVideoGenerator(frame_size=frame_size)
        
        # Validate keywords
        if not self.keywords:
            raise ValueError("No keywords provided for the segment")
        
        # Create a temporary directory for intermediate files
    
        try:
            # Generate audio for the segment
            audio_segment = audio_generator.from_text(self.text)
            
            # Create the complete video with audio using the enhanced method
            final_video = video_generator.from_key_words(
                keywords=self.keywords,
                giphy_api_key=giphy_api_key,
                audio_segment=audio_segment,
            )
            
            # Verify output
            if final_video:
                if output_path and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    try:
                        final_video.write_videofile(
                            output_path,
                            codec=codec,
                            audio_codec=audio_codec,
                            fps=fps,
                            audio_bitrate=audio_bitrate
                        )
                        print(f"Video with audio created successfully: {output_path}")
                    except Exception as e:
                        print(f"Error saving video to {output_path}: {str(e)}")
                        return None
                    print(f"Video created successfully: {output_path}")
                    return output_path
                else:
                    return final_video
            else:
                print("Video creation failed")
                return None
                
        except Exception as e:
            print(f"Error exporting segment to video: {str(e)}")
            return None

class ComedyScript(BaseModel):
    title: str = Field(
        description="A catchy, satirical title for the comedy piece - should be humorous "
        "and capture the essence of the original news with an ironic twist."
    )

    description: str = Field(
        description="A brief description of the satirical take on the news article. "
        "Should explain the comedic angle in 1-2 sentences."
    )

    topic_tags: List[str] = Field(
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
        output_path: str|None=None,
        frame_size=(1280, 720),
        codec="libx264",
        audio_codec="libmp3lame",
        fps=24,
        audio_bitrate="192k"
    ):
        # Create a temporary directory for intermediate files
        try:
            # Process each segment into a video clip
            segment_clips = []
            
            for i, segment in enumerate(self.segments):
                print(f"Processing segment {i+1} of {len(self.segments)}")
                
                # Generate video for this segment (but don't write to file yet)
                segment_clip = segment.convert_to_video(
                    elevenlabs_api_key=elevenlabs_api_key,
                    giphy_api_key=giphy_api_key,
                    output_path=None,  # Don't export individual segments
                    frame_size=frame_size
                )
                
                if segment_clip and isinstance(segment_clip, CompositeVideoClip):
                    segment_clips.append(segment_clip)
                else:
                    print(f"Failed to create video for segment {i+1}")
            
            if not segment_clips:
                print("No segment videos were successfully created")
                return None
            
            # Concatenate all segment clips
            print(f"Concatenating {len(segment_clips)} segment videos")
            final_video = concatenate_videoclips(segment_clips)
            
            # Add title if needed (could be implemented as text overlay)
            # final_video = self._add_title_overlay(final_video, self.title)
            
            # Export if output path is provided
            if output_path:
                try:
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
                except Exception as e:
                    print(f"Error saving final video to {output_path}: {str(e)}")
                    return None
            else:
                # Return the composite video clip for further processing
                return final_video
                
        except Exception as e:
            print(f"Error creating comedy script video: {str(e)}")
            return None

    # Optional method for adding title overlay - could be implemented if needed
    # def _add_title_overlay(self, video_clip, title_text):
    #     # Create a text clip with the title
    #     # Add it as an overlay to the video
    #     # Return the combined clip
    #     pass