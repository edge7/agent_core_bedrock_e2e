from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CV_AGENT_", env_file=".env", extra="ignore")

    model_id: str = "global.anthropic.claude-sonnet-4-6"
    host: str = "127.0.0.1"
    port: int = 8000

    # The CV is loaded from AWS Secrets Manager (personal data stays out of
    # the repo and out of the deployment bundle). If the secret is not
    # reachable, the agent falls back to the local data/cv.md file.
    cv_secret_name: str | None = "cv-agent/cv"
    # Private bucket holding cv.pdf, served via short-lived presigned URLs.
    cv_bucket: str = "ed7-cv-agent-assets"
    aws_region: str = Field("eu-west-1", validation_alias="AWS_REGION")

    # Pushover credentials keep their original names (no CV_AGENT_ prefix).
    # When the env vars are absent and pushover_secret_name is set, they are
    # fetched from AWS Secrets Manager instead (JSON: user_key, api_token).
    pushover_user_key: str | None = Field(None, validation_alias="PUSHOVER_USER_KEY")
    pushover_api_token: str | None = Field(None, validation_alias="PUSHOVER_API_TOKEN")
    pushover_secret_name: str | None = "cv-agent/pushover"

    def resolve_pushover(self) -> tuple[str | None, str | None]:
        if self.pushover_user_key and self.pushover_api_token:
            return self.pushover_user_key, self.pushover_api_token
        if self.pushover_secret_name:
            try:
                import json

                import boto3

                client = boto3.client("secretsmanager", region_name=self.aws_region)
                data = json.loads(
                    client.get_secret_value(SecretId=self.pushover_secret_name)["SecretString"]
                )
                self.pushover_user_key = data.get("user_key")
                self.pushover_api_token = data.get("api_token")
            except Exception:
                import logging

                logging.getLogger(__name__).exception(
                    "could not read pushover secret %r", self.pushover_secret_name
                )
        return self.pushover_user_key, self.pushover_api_token


settings = Settings()
