from ccfarm.agents.satirist.models import ComedyScript
from ccfarm.agents.satirist.satirist import Satirist
from prefect import flow, get_run_logger
from prefect.blocks.system import Secret
from ccfarm.clients.news_client import NewsAPIClient
from ccfarm.persistence.scores_storage import ArticleScoresStore
from ccfarm.persistence.script_storage import ScriptStorage

# Function to get top articles (no @task)
def get_top_articles(
    scores_storage: ArticleScoresStore,
    script_storage: ScriptStorage,
    limit: int = 5,
    reanalyze_existing: bool = False
):
    logger = get_run_logger()
    logger.info(f"Retrieving top articles (limit: {limit}, reanalyze: {reanalyze_existing})")

    scored_articles = scores_storage.list_scores()
    if not scored_articles:
        logger.warning("No scored articles found in storage")
        return []

    if reanalyze_existing:
        return scored_articles[:limit]

    try:
        existing_scripts = script_storage.get_all_scripts(limit=1000)
        script_article_ids = {script.get("source_article") for script in existing_scripts}
        logger.info(f"Found {len(script_article_ids)} processed article IDs to filter against")
    except Exception as e:
        logger.error(f"Error retrieving existing scripts: {e}")
        script_article_ids = set()

    filtered_articles = [
        article for article in scored_articles if article.get("_id") not in script_article_ids
    ]
    logger.info(f"Filtered out {len(scored_articles) - len(filtered_articles)} already processed articles")
    return filtered_articles[:limit]

# Combined function to process articles and store scripts (no @task)
def process_and_store_scripts(
    satirist: Satirist,
    script_storage: ScriptStorage,
    articles: list[dict]
):
    logger = get_run_logger()
    processed_scripts = []
    stored_ids = []

    if not articles:
        logger.info("No articles to process")
        return [], []

    logger.info(f"Starting processing of {len(articles)} articles")
    processed_scripts = satirist.process_articles(articles)

    for i, script in enumerate(processed_scripts):
        try:
            article_id = articles[i].get("_id", f"unknown-{i}")
            script_id = script_storage.store_script(
                title=script.title,
                script_data=script.model_dump(),
                source_article=article_id
            )
            stored_ids.append(script_id)
            logger.info(f"Processed and stored script {script_id} for article {article_id}")
        except Exception as e:
            logger.error(f"Error processing/storing script for article {article_id}: {e}")

    return processed_scripts, stored_ids

# Function to generate summary (no @task)
def generate_results_summary(
    processed_scripts: list[ComedyScript],
    stored_ids: list[str]
):
    logger = get_run_logger()

    if not processed_scripts:
        message = "No scripts were generated in this run"
        logger.info(message)
        return message

    summary_lines = [f"Generated {len(processed_scripts)} comedy scripts:"]
    for i, script in enumerate(processed_scripts):
        script_id = stored_ids[i] if i < len(stored_ids) else "not stored"
        summary_lines.append(f"\n{i+1}. {script.title}")
        summary_lines.append(f"   ID: {script_id}")
        summary_lines.append(f"   Segments:")
        for segment in script.segments:
            summary_lines.append(f"   {segment.text}...")

    summary = "\n".join(summary_lines)
    logger.info(f"\nGeneration Summary:\n{summary}")
    return summary

@flow(name="Comedy Script Generation Flow")
def satirist_flow(
    articles_limit: int = 1,
    reanalyze_existing: bool = False,
    mongodb_conn_secret_block: str = "dev-mongodb-conn-string",
    anthropic_api_secret_block: str = "anthropic-api-key",
    news_api_secret_block: str = "news-api-key",
):
    logger = get_run_logger()
    logger.info(f"Starting satirist flow with limit {articles_limit}")

    # Initialize clients and storage
    conn_string = Secret.load(mongodb_conn_secret_block).get()
    script_storage = ScriptStorage(conn_string)
    scores_storage = ArticleScoresStore(conn_string)
    anthropic_api_key = Secret.load(anthropic_api_secret_block).get()
    news_api_key = Secret.load(news_api_secret_block).get()
    news_client = NewsAPIClient(news_api_key)
    satirist = Satirist(anthropic_api_key=anthropic_api_key, news_client=news_client)

    # Step 1: Get top articles
    top_articles = get_top_articles(scores_storage, script_storage, articles_limit, reanalyze_existing)
    if not top_articles:
        logger.warning("No articles found to process")
        return []

    # Step 2: Process and store scripts
    processed_scripts, stored_ids = process_and_store_scripts(satirist, script_storage, top_articles)

    # Step 3: Generate summary
    generate_results_summary(processed_scripts, stored_ids)

    logger.info("Satirist flow completed successfully")
    return processed_scripts

if __name__ == "__main__":
    satirist_flow()