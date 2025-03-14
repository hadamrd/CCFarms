import os
import re
from ccfarm.agents.scout.scorer import ArticleScorer
from ccfarm.agents.satirist.satirist import Satirist
from ccfarm.media.youtube_upload import upload_video_to_youtube
from prefect import flow, get_run_logger
from prefect.blocks.system import Secret
from ccfarm.clients.news_client import NewsAPIClient
from ccfarm.persistence.scores_storage import ArticleScoresStore
from ccfarm.persistence.script_storage import ScriptStorage


@flow(name="Comedy Script Generation Flow")
def satirist_flow(
    query: str = "snapchat outage",
    nbr_articles_to_scout: int = 20,
    days_in_past: int = 7,
    language: str = "en",
    sort_by: str = "relevancy",
    nbr_of_articles_to_use: int = 5,
    environment: str = "dev",
    output_dir: str = "./videos",
    frame_size: tuple[int, int] = (1280, 720),
    codec: str = "libx264",
    audio_codec: str = "libmp3lame",
    fps: int = 24,
    audio_bitrate: str = "192k"
):
    logger = get_run_logger()
    logger.info(f"Starting satirist flow with limit {nbr_of_articles_to_use}")

    # Step 1: Initialize clients, storage and agents
    if environment == "dev":
        conn_string = Secret.load("dev-mongodb-conn-string").get()
    else:
        raise ValueError("Invalid environment specified")
    
    anthropic_api_key = Secret.load("anthropic-api-key").get()
    news_api_key = Secret.load("news-api-key").get()
    elevenlabs_api_key = Secret.load("elevenlabs-api-key").get()
    giphy_api_key = Secret.load("giphy-api-key").get()
    unsplash_api_key = Secret.load("unsplash-api-key").get()

    news_client = NewsAPIClient(news_api_key)
    
    script_storage = ScriptStorage(conn_string)
    scores_storage = ArticleScoresStore(conn_string)
    
    satirist = Satirist(anthropic_api_key=anthropic_api_key, news_client=news_client)
    scorer = ArticleScorer(
        anthropic_api_key=anthropic_api_key, news_client=news_client, scores_store=scores_storage
    )

    # Step 2: Scout and score articles sorted by the given score
    top_articles = scorer.dig_for_news(
        query=query,
        page_size=nbr_articles_to_scout,
        days_in_past=days_in_past,
        sort_by=sort_by,
        language=language,
    )

    if not top_articles:
        logger.warning("No articles found to process")
        return []

    logger.info(f"Processing {len(top_articles)} articles into one script")
    # Generate one script from all articles
    script = satirist.process_articles(top_articles)

    # Store the script with all source article IDs
    article_urls = [
        article.get("url", f"unknown-{i}") for i, article in enumerate(top_articles)
    ]
    script_id = script_storage.store_script(
        title=script.title, script_data=script.model_dump(), source_articles=article_urls
    )
    logger.info(f"Stored multi-article script {script_id} for articles {article_urls}")

    # Step 4: Convert the script to a video
    logger.info(f"Converting script {script.title} to video")
    
    # Sanitize title for filename
    sanitized_title = re.sub(r'[^\w\s-]', '', script.title).strip().lower()
    sanitized_title = re.sub(r'[-\s]+', '-', sanitized_title)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{sanitized_title}.mp4")
    logger.info(f"Video will be saved to: {output_path}")
    
    script.convert_to_video(
        elevenlabs_api_key=elevenlabs_api_key,
        giphy_api_key=giphy_api_key,
        unsplash_api_key=unsplash_api_key,
        output_path=output_path,
        frame_size=frame_size,
        codec=codec,
        audio_codec=audio_codec,
        fps=fps,
        audio_bitrate=audio_bitrate,
    )

    # Step 5: Upload the video to YouTube
    logger.info(f"Uploading video to YouTube")
    video_link = upload_video_to_youtube(
        video_path=output_path,
        title=script.title,
        description=script.description,
        tags=script.topic_tags
    )
    
    logger.info(f"Video uploaded successfully. Link: {video_link}")

    
if __name__ == "__main__":
    video_link = satirist_flow()
    if video_link:
        print(f"Video published at: {video_link}")
    else:
        print("No video link was returned")