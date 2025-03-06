# src/orchestration_play/agents/weather/weather_agent.py
import os
import json
import requests
from typing import Dict, Optional
from prefect import get_run_logger

from ..orchestration_play.agents.schema_agent import SchemaAgent

class WeatherReporter(SchemaAgent):
    """
    A simple weather reporter agent that generates weather reports
    based on real data from a weather API.
    """
    
    def __init__(
        self, 
        anthropic_api_key: str, 
        model: str = "claude-3-5-sonnet-20241022",
        schema_file: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize the Weather Reporter agent.
        
        Args:
            anthropic_api_key: API key for Anthropic
            model: Anthropic model to use
            schema_file: Path to JSON schema file (optional)
            api_key: Weather API key (optional)
        """
        # Set up the directory for this agent
        self.agent_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Load schema from file or use default
        schema_path = schema_file or os.path.join(
            self.agent_dir, 
            "weather_schema.json"
        )
        
        # Load schema from file
        with open(schema_path, 'r') as f:
            response_schema = json.load(f)
        
        # Initialize base agent with JSON schema
        super().__init__(
            name="WeatherReporter",
            response_schema=response_schema,
            anthropic_api_key=anthropic_api_key,
            model=model,
            template_dir=self.agent_dir,
            response_tag="weather_report"
        )
        
        self.logger = get_run_logger()
        self.api_key = api_key
    
    def get_weather_data(self, location: str) -> Dict:
        """
        Get weather data from a public API.
        
        Args:
            location: Location to get weather for
            
        Returns:
            Dictionary of weather data
        """

        try:
            self.logger.info(f"Fetching weather data for {location}")
            
            # Use wttr.in as a simple, free weather API
            url = f"https://wttr.in/{location}?format=j1"
            response = requests.get(url)
            response.raise_for_status()
            
            weather_data = response.json()
            self.logger.info(f"Successfully fetched weather data for {location}")
            
            return weather_data
            
        except Exception as e:
            self.logger.error(f"Error fetching weather data: {str(e)}")
            # Return minimal placeholder data if API fails
            return {
                "current_condition": [
                    {
                        "temp_C": "N/A",
                        "weatherDesc": [{"value": "Unknown"}],
                        "windspeedKmph": "N/A",
                        "humidity": "N/A"
                    }
                ],
                "nearest_area": [
                    {
                        "areaName": [{"value": location}]
                    }
                ],
                "weather": []
            }
    
    def generate_weather_report(self, location: str) -> Dict:
        """
        Generate a weather report for the given location.
        
        Args:
            location: Location to generate report for
            
        Returns:
            Structured weather report
        """
        try:
            self.logger.info(f"Generating weather report for {location}")
            
            # Get weather data
            weather_data = self.get_weather_data(location)
            
            # Extract key data for prompt
            current = weather_data.get("current_condition", [{}])[0]
            forecast = weather_data.get("weather", [])
            
            # Use the base agent's process method with the weather_prompt.j2 template
            report = self.process(
                prompt_template="weather_prompt.j2",
                location=location,
                current_temp=f"{current.get('temp_C', 'N/A')}°C",
                current_desc=current.get('weatherDesc', [{}])[0].get('value', 'Unknown'),
                wind_speed=f"{current.get('windspeedKmph', 'N/A')} km/h",
                humidity=f"{current.get('humidity', 'N/A')}%",
                forecast_data=forecast
            )
            
            self.logger.info(f"Successfully generated weather report for {location}")
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating weather report: {str(e)}")
            raise