"""The CV/personal-brand agent.

Platform-agnostic by design: the same Agent object runs locally (CLI, web
harness) and inside AgentCore Runtime via the wrapper in runtime.py.
"""

import logging
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.models.bedrock import BedrockConverseModel, BedrockModelSettings

from cv_agent.pushover import send_pushover
from cv_agent.settings import settings

CV_PATH = Path(__file__).parent / "data" / "cv.md"


def load_cv() -> str:
    """Load the CV from Secrets Manager, falling back to the local file."""
    if settings.cv_secret_name:
        try:
            import boto3

            client = boto3.client("secretsmanager", region_name=settings.aws_region)
            return client.get_secret_value(SecretId=settings.cv_secret_name)["SecretString"]
        except Exception:
            pass  # no AWS access or secret missing — try the local file
    if CV_PATH.exists():
        return CV_PATH.read_text()
    raise RuntimeError(
        "No CV available: point CV_AGENT_CV_SECRET_NAME at a readable secret "
        f"or create {CV_PATH} (see data/cv.example.md for the structure)."
    )

INSTRUCTIONS_TEMPLATE = """\
You are the professional assistant for the person described in the CV below.
Recruiters and potential collaborators chat with you to learn about them.

Rules:
- Answer only from the CV content. If something isn't covered, say you don't
  have that information and offer to pass the question along via the
  record_recruiter_contact tool.
- Be warm, concise, and professional. You represent someone's personal brand.
- Respect the "What the agent should NOT discuss" section strictly.

Lead capture — your most important job:
- The MOMENT the conversation contains a recruiter's name AND a way to reach
  them, call record_recruiter_contact immediately with whatever details you
  have. Do not wait for more information, do not ask for permission, do not
  merely promise to pass it along. Capture first, ask follow-ups after.
- If a recruiter shows any interest (a role in mind, wants a call, asks about
  availability) but hasn't left contact details, actively ask for their name
  and email — once captured, call the tool right away.
- Never say or imply the CV owner has been notified unless the tool was
  actually called and returned success. If it failed, apologize and give the
  direct email instead.

- If someone asks for the CV, the resume, or a PDF copy, use
  get_cv_download_link and share the link (it expires in 15 minutes — say so).
- Never invent experience, skills, or availability.

=== CV ===
{cv}
=== END CV ===
"""


def build_agent() -> Agent[None, str]:
    model = BedrockConverseModel(settings.model_id)
    agent = Agent(
        model,
        instructions=INSTRUCTIONS_TEMPLATE.format(cv=load_cv()),
        # The system prompt embeds the whole CV (~4k tokens): caching it cuts
        # its cost ~10x on every turn after the first (5-minute TTL).
        model_settings=BedrockModelSettings(bedrock_cache_instructions=True),
    )

    @agent.tool_plain
    def record_recruiter_contact(
        name: str,
        company: str,
        contact: str,
        message: str,
    ) -> str:
        """Notify the CV owner that a recruiter wants to get in touch.

        Call this as soon as the conversation contains a recruiter's name and
        a way to reach them — even if other details are still missing.

        Args:
            name: The recruiter's name.
            company: The company they represent.
            contact: Email address or other way to reach them.
            message: What the opportunity or question is about.
        """
        logging.getLogger(__name__).info(
            "record_recruiter_contact called: %s (%s)", name, company
        )
        notified = send_pushover(
            f"👤 {name} ({company})\n📫 {contact}\n\n{message}"
        )
        if notified:
            return "The CV owner has been notified and will follow up."
        return (
            "The notification could not be delivered right now. "
            "Apologize and suggest the recruiter email the CV owner directly."
        )

    @agent.tool_plain
    def get_cv_download_link() -> str:
        """Generate a short-lived download link for the CV as a PDF.

        Call this whenever someone asks for the CV, the resume, or a PDF copy.
        """
        import boto3
        from botocore.config import Config

        logging.getLogger(__name__).info("get_cv_download_link called")
        # Regional endpoint is mandatory: presigning against the global
        # endpoint yields a 307 redirect that invalidates the signature.
        client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            endpoint_url=f"https://s3.{settings.aws_region}.amazonaws.com",
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.cv_bucket, "Key": "cv.pdf"},
            ExpiresIn=900,
        )
        send_pushover("📄 Someone requested the CV download link.", title="CV Agent — CV requested")
        return (
            f"Here is the download link (valid for 15 minutes): {url}\n"
            "Present it as a markdown link labelled 'Download Enrico's CV (PDF)'."
        )

    return agent
