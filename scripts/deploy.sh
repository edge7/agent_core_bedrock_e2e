#!/usr/bin/env bash
# Deploy the CV agent to Amazon Bedrock AgentCore Runtime.
#
# ── One-time prerequisites ───────────────────────────────────────────────────
#   npm install -g @aws/agentcore     # the AgentCore CLI (CDK-based)
#   npx cdk bootstrap                  # once per AWS account+region (CDK needs it)
#   AWS credentials in the environment with permissions to create
#   CloudFormation stacks, IAM roles, and AgentCore resources.
#
# ── What lives where ─────────────────────────────────────────────────────────
#   agentcore/agentcore.json   project config: the runtime definition
#                              (CodeZip build, entrypoint main.py, env vars
#                              pointing at the two Secrets Manager secrets)
#   agentcore/cdk/             the CDK app that turns that config into a
#                              CloudFormation stack
#   app/                       the deployable code: only this directory gets
#                              bundled (main.py entrypoint + src/cv_agent)
#
# ── What `agentcore deploy` actually does ────────────────────────────────────
#   1. bundles this directory into a code zip (no Docker involved)
#   2. runs `cdk deploy`: CloudFormation creates/updates
#        - the AgentCore Runtime (managed Python 3.13)
#        - its IAM execution role (we extend it below for the secrets)
#        - OTEL instrumentation wiring (traces to CloudWatch)
#   3. prints the runtime ARN and endpoint

set -euo pipefail
cd "$(dirname "$0")/.."

STACK_NAME="AgentCore-cvagent-default"   # <project>-<target> from agentcore.json
REGION="eu-west-1"

# Deploy (CDK synth + CloudFormation). --yes skips the approval prompt.
agentcore deploy --yes

# The execution role must be able to read our two secrets at startup
# (the agent loads the CV and the Pushover keys from Secrets Manager).
# The CLI generates the role; we attach a least-privilege inline policy.
ROLE_NAME=$(aws cloudformation describe-stack-resources \
  --stack-name "$STACK_NAME" --region "$REGION" \
  --query "StackResources[?ResourceType=='AWS::IAM::Role'&&contains(LogicalResourceId,'Runtime')].PhysicalResourceId | [0]" \
  --output text)
echo "Runtime execution role: $ROLE_NAME"

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name read-cv-agent-secrets \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": "secretsmanager:GetSecretValue",
        "Resource": "arn:aws:secretsmanager:eu-west-1:103504787248:secret:cv-agent/*"
      },
      {
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": "arn:aws:s3:::ed7-cv-agent-assets/cv.pdf"
      }
    ]
  }'
echo "Secrets + CV bucket policy attached."

# Smoke test: one streamed invocation against the deployed runtime.
agentcore invoke "In one sentence, who are you?" --stream

# ── Day-2 commands ───────────────────────────────────────────────────────────
#   agentcore status            # runtime details (ARN, endpoint, state)
#   agentcore invoke "..."      # ad-hoc invocation (add --stream for SSE)
#   agentcore logs              # stream runtime logs from CloudWatch
#   agentcore dev               # run the agent locally with hot reload
#   agentcore destroy           # tear the whole stack down
