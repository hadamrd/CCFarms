# src/orchestration_play/flows/weather_flow.py
from prefect import flow, task, get_run_logger
from datetime import datetime
import requests
from anthropic import Anthropic
from prefect.blocks.system import Secret
from prefect.artifacts import create_markdown_artifact

from orchestration_play.blocks import TeamsWebhook


@task(name="Fetch Weather Data", retries=3)
def fetch_weather_data(location="London"):
    """Fetch weather data from a public API."""
    url = f"https://wttr.in/{location}?format=j1"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


@task(name="Process Weather Data")
def process_weather_data(weather_data):
    """Process the raw weather data."""
    current_condition = weather_data.get("current_condition", [{}])[0]
    nearest_area = weather_data.get("nearest_area", [{}])[0]
    area_name = nearest_area.get("areaName", [{}])[0].get("value", "Unknown")

    processed_data = {
        "current_temp": f"{current_condition.get('temp_C', 'N/A')}°C",
        "wind": f"{current_condition.get('windspeedMiles', 'N/A')} mph",
        "description": current_condition.get("weatherDesc", [{}])[0].get(
            "value", "N/A"
        ),
        "location": area_name,
        "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return processed_data


@task(name="Generate Creative Summary", retries=2)
def generate_creative_summary(processed_data):
    """Generate a fun weather summary using Claude."""
    logger = get_run_logger()
    try:
        # Retrieve API key from Prefect secrets
        secret_block = Secret.load("anthropic-api-key")
        api_key = secret_block.get()

        client = Anthropic(api_key=api_key)

        prompt = f"""Create a fun, engaging weather report for {processed_data['location']} using this data:
        - Temperature: {processed_data['current_temp']}
        - Wind: {processed_data['wind']}
        - Conditions: {processed_data['description']}
        
        Add appropriate emojis, a creative analogy, and one funny recommendation for clothing or activities.
        Format it like a friendly TV weather presenter would!"""

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text
    except Exception as e:
        logger.error(f"Creative summary failed: {e}")
        return "Could not generate creative summary - but the weather is still interesting!"


@task(name="Save Report")
def save_report(report, location):
    """Save the report to a file and create a Prefect artifact."""
    # Save to local file
    filename = f"{location.lower()}_weather_report.txt"
    with open(filename, "w") as f:
        f.write(report)

    # Create Prefect artifact
    artifact_id = create_markdown_artifact(
        key=f"weather-report-{location.lower()}",
        markdown=report,
        description=f"Weather report for {location}",
    )

    return filename, artifact_id


@flow(name="Weather Report Generator")
def weather_ai_report_flow_with_teams_notif(location="London"):
    """Main workflow with creative AI enhancements."""
    try:
        # Fetch and process data
        weather_data = fetch_weather_data(location)
        processed_data = process_weather_data(weather_data)

        # Generate both standard and creative reports
        creative_summary = generate_creative_summary(processed_data)

        # Build final report
        report = f"""🌤️✨ WEATHER WONDERS REPORT ✨🌤️
    Location: {processed_data['location']}
    Generated at: {processed_data['processed_at']}

    📊 Standard Data:
    - Temperature: {processed_data['current_temp']}
    - Wind: {processed_data['wind']}
    - Conditions: {processed_data['description']}

    🎭 AI-Powered Creative Summary:
    {creative_summary}

    🌍 Stay weather-aware and have a great day!"""

        # Save and return
        filename, artifact_id = save_report(report, location)
        print(f"Weather report saved to {filename} and artifact {artifact_id}")
    except Exception as e:
        teams_block = TeamsWebhook.load("weather-teams-webhook")
        teams_block.notify(f"🔥 Flow failed for {location}: {str(e)[:200]}")
        raise

    # Send success notification with the AI creative summary
    success_message = (
        f"✅ Weather Update for {location}\n\n"
        f"{creative_summary}\n\n"
        f"🔗 See full report in Prefect UI"
    )

    teams_block = TeamsWebhook.load("weather-teams-webhook")
    teams_block.notify(success_message)

    return filename

if __name__ == "__main__":
    weather_ai_report_flow_with_teams_notif("Paris")
