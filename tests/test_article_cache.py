from ccfarm.blocks import ArticleCacheBlock


if __name__ == "__main__":
    block: ArticleCacheBlock = ArticleCacheBlock.load("dev-article-cache")
    cache = block.get_store()
    print(cache.list_scores())
