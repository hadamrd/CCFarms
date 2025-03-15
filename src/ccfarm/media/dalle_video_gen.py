import os
import tempfile
from typing import cast
from moviepy import AudioFileClip, ImageClip, CompositeVideoClip
from moviepy.video import fx
from pydub import AudioSegment
from ccfarm.agents.illustrator.comic_illustrator import ComicIllustrator


class DalleVideoGenerator:
    """
    An advanced video generator that uses DALL-E 3 generated images.
    This handles the conversion of multiple AI-generated images into a composite video.
    """

    def __init__(
        self,
        anthropic_api_key: str,
        openai_api_key: str,
        frame_size: tuple[int, int] = (1280, 720)
    ):
        self.frame_size = frame_size
        self.comic_illustrator = None
        self.comic_illustrator = ComicIllustrator(
            anthropic_api_key=anthropic_api_key, openai_api_key=openai_api_key
        )

    def create_video_from_images(
        self,
        image_paths: list[str],
        total_duration: float,
        output_path: str|None = None,
        transition_duration: float = 0.5,
    ) -> CompositeVideoClip:
        if not image_paths:
            raise ValueError("No image paths provided")

        print(
            f"Creating video from {len(image_paths)} images with total duration of {total_duration:.2f} seconds"
        )

        # Calculate duration for each image (accounting for transitions)
        total_transition_time = transition_duration * (len(image_paths) - 1)
        image_display_time = (total_duration - total_transition_time) / len(image_paths)
        print(
            f"Each image will display for {image_display_time:.2f} seconds with {transition_duration:.2f}s transitions"
        )

        video_clips = []
        current_time = 0.0

        for i, path in enumerate(image_paths):
            print(f"Processing image: {os.path.basename(path)}")

            # Create ImageClip
            clip = ImageClip(path, duration=image_display_time + transition_duration)

            # Resize to fit frame size while maintaining aspect ratio
            clip = cast(ImageClip, clip.resized(height=self.frame_size[1]))

            # Center the clip horizontally
            w, h = clip.size
            pos = ((self.frame_size[0] - w) / 2, 0)

            # Position clip with start time
            positioned_clip = clip.with_position(pos).with_start(current_time)

            # Add fade in/out effects except for first and last clips
            if i > 0:
                positioned_clip = positioned_clip.with_effects([fx.FadeIn(duration=transition_duration / 2)])
            if i < len(image_paths) - 1:
                positioned_clip = positioned_clip.with_effects([fx.FadeOut(duration=transition_duration / 2)])

            video_clips.append(positioned_clip)
            current_time += image_display_time

        # Create the composite video with a black background
        composite_video = CompositeVideoClip(video_clips, size=self.frame_size, bg_color=(0, 0, 0))

        if output_path:
            composite_video.write_videofile(output_path, codec="libx264", fps=24)

        return composite_video

    def generate_images_for_text(self, text: str) -> list[str]:
        """
        Generate DALL-E images for a speech segment using the ComicIllustrator agent.

        Args:
            text: The text content of the speech segment

        Returns:
            List of paths to the generated images
        """
        if not self.comic_illustrator:
            raise ValueError("ComicIllustrator not initialized. API keys required.")

        with tempfile.TemporaryDirectory() as temp_dir:
            # Generate images using ComicIllustrator
            image_paths = self.comic_illustrator.generate_images(
                text=text, 
                output_dir=temp_dir
            )

            # If no images were generated, raise an error
            if not image_paths:
                raise ValueError(f"Failed to generate any images for segment")

            # Return the list of image paths
            return image_paths # type: ignore

    def from_text(
        self, text: str, audio: AudioSegment, output_path: str|None = None
    ) -> CompositeVideoClip|None:
        """
        Create a video for a speech segment by generating DALL-E images and syncing with audio.

        Args:
            segment_text: The text content of the speech segment
            audio_segment: The audio recording of the segment
            output_path: Optional path to save the output video

        Returns:
            A CompositeVideoClip of the segment video, or None if generation failed
        """
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Generate DALL-E images
                image_paths = self.generate_images_for_text(text)

                if not image_paths:
                    print(f"No images could be generated for segment")
                    return None

                # Save audio to temporary file
                temp_audio_path = os.path.join(temp_dir, "temp_audio.mp3")
                audio.export(temp_audio_path, format="mp3")
                audio_clip = AudioFileClip(temp_audio_path)

                # Create video from images
                video = self.create_video_from_images(
                    image_paths=image_paths, total_duration=audio_clip.duration
                )

                # Add audio to video
                final_video = video.with_audio(audio_clip)

                # Save video if output path provided
                if output_path:
                    final_video.write_videofile(
                        output_path, codec="libx264", audio_codec="libmp3lame", fps=24
                    )

                return final_video

        except Exception as e:
            print(f"Error creating video for segment : {str(e)}")
            return None
