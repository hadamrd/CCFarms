from orchestration_play.blocks import ArticleCacheBlock


if __name__ == "__main__":
    block: ArticleCacheBlock = ArticleCacheBlock.load("dev-article-cache")
    cache = block.get_article_cache()
    print(cache.get_all_cached())
