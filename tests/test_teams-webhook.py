from ccfarm.blocks import TeamsWebhook


if __name__ == "__main__":
    teams = TeamsWebhook.load("weather-teams-webhook")
    teams.notify("🚀 Testing Prefect Teams integration!")
