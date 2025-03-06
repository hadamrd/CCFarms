# Example usage of the WeatherReporter agent
from draft.weather_agent import WeatherReporter
from prefect import flow, task, get_run_logger
from prefect.blocks.system import Secret
from prefect.artifacts import create_markdown_artifact
import json


@task(name="Generate Weather Report")
def generate_weather_report(api_key: str, location: str):
    """
    Generate a weather report for the specified location.
    
    Args:
        api_key: Anthropic API key
        location: Location to generate weather report for
        
    Returns:
        Weather report dictionary
    """
    logger = get_run_logger()
    
    # Initialize the agent
    logger.info(f"Initializing WeatherReporter agent for {location}")
    agent = WeatherReporter(anthropic_api_key=api_key)
    
    # Generate the report
    logger.info(f"Generating weather report for {location}")
    report = agent.generate_weather_report(location)
    
    return report

@task(name="Create Report Artifact")
def create_report_artifact(report: dict, location: str):
    """
    Create a markdown artifact from the weather report.
    
    Args:
        report: Weather report dictionary
        location: Location the report is for
        
    Returns:
        Artifact ID
    """
    logger = get_run_logger()
    
    # Format the report as markdown
    current = report["current_conditions"]
    
    markdown = f"""# Weather Report for {location}

## Current Conditions
- **Temperature:** {current["temperature"]}
- **Description:** {current["description"]}
- **Wind:** {current["wind"]}
- **Humidity:** {current["humidity"]}

## Forecast
| Day | High | Low | Description |
|-----|------|-----|-------------|
"""
    
    for day in report["forecast"]:
        markdown += f"| {day['day']} | {day['high']} | {day['low']} | {day['description']} |\n"
    
    markdown += "\n## Recommendations\n\n"
    markdown += "### Clothing\n"
    for item in report["recommendations"]["clothing"]:
        markdown += f"- {item}\n"
    
    markdown += "\n### Recommended Activities\n"
    for activity in report["recommendations"]["activities"]["recommended"]:
        markdown += f"- {activity}\n"
    
    markdown += "\n### Not Recommended\n"
    for activity in report["recommendations"]["activities"]["not_recommended"]:
        markdown += f"- {activity}\n"
    
    # Create the artifact
    logger.info(f"Creating report artifact for {location}")
    artifact_id = create_markdown_artifact(
        key=f"weather-report-{location.lower().replace(' ', '-')}",
        markdown=markdown,
        description=f"Weather Report for {location}"
    )
    
    return artifact_id

@flow(name="Weather Report Flow")
def weather_report_flow(location: str = "London"):
    """
    Flow to generate and display a weather report.
    
    Args:
        location: Location to generate report for
    """
    logger = get_run_logger()
    logger.info(f"Starting weather report flow for {location}")
    
    # Get API key from Secret block
    secret_block = Secret.load("anthropic-api-key")
    api_key = secret_block.get()
    
    # Generate the report
    report = generate_weather_report(api_key, location)
    
    # Create an artifact
    artifact_id = create_report_artifact(report, location)
    
    logger.info(f"Weather report flow completed with artifact ID: {artifact_id}")
    return report

if __name__ == "__main__":
    # Run the flow
    report = weather_report_flow("Paris")
    print(json.dumps(report, indent=2))